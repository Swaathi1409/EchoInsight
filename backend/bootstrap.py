import yaml
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone
import hashlib
import json
import logging

from backend.models import QAChecklist, QAChecklistVersion, QAChecklistItem

logger = logging.getLogger(__name__)

POLICY_DIR = Path(__file__).parent / "config"

def _compute_hash(data: dict) -> str:
    s = json.dumps(data, sort_keys=True)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

async def bootstrap_qa_checklists(session: AsyncSession) -> None:
    """Idempotently seed the QA checklists from YAML files."""
    for p in sorted(POLICY_DIR.glob("policy_*.yaml")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            version_str = p.stem.replace("policy_", "")
            
            # YAML format is a bit loose. Expected fields based on policy_example_v1.yaml:
            checklist_key = version_str.split("_v")[0] if "_v" in version_str else version_str
            version_num = int(data.get("version", 1))
            name = data.get("label", f"Checklist {checklist_key}")
            
            # Find or create QAChecklist
            q = select(QAChecklist).where(QAChecklist.key == checklist_key)
            result = await session.execute(q)
            checklist = result.scalar_one_or_none()
            if not checklist:
                checklist = QAChecklist(
                    key=checklist_key,
                    name=name,
                    description=f"Auto-bootstrapped checklist {checklist_key}"
                )
                session.add(checklist)
                await session.flush()
                logger.info(f"Created QA Checklist: {checklist_key}")
            
            # Check if this exact version exists
            content_hash = _compute_hash(data)
            q_ver = select(QAChecklistVersion).where(
                QAChecklistVersion.checklist_id == checklist.id,
                QAChecklistVersion.version_number == version_num
            )
            ver = (await session.execute(q_ver)).scalar_one_or_none()
            
            if ver:
                # If exists, continue. Idempotent.
                continue
            
            # Create version
            settings = {
                "scoring": data.get("scoring", {}),
                "churn_risk_signals": data.get("churn_risk_signals", {})
            }
            
            ver = QAChecklistVersion(
                checklist_id=checklist.id,
                version_number=version_num,
                status="active",
                source="yaml_seed",
                created_by="system",
                created_at=datetime.now(timezone.utc),
                content_hash=content_hash,
                settings=settings,
            )
            session.add(ver)
            await session.flush()
            logger.info(f"Created QA Checklist Version: {checklist_key} v{version_num}")
            
            # Create items
            items_data = data.get("checklist_items", [])
            for idx, item in enumerate(items_data):
                db_item = QAChecklistItem(
                    version_id=ver.id,
                    item_key=item["id"],
                    display_name=item["display"],
                    description=item.get("description"),
                    weight=float(item.get("weight", 1.0)),
                    required=item.get("required", False),
                    critical=item.get("critical", False),
                    enabled=True,
                    display_order=idx,
                    evaluation_type=item.get("assessment_method", "quote" if item.get("evidence_type") == "quote" else "llm_contextual"),
                    policy_reference=item.get("policy_reference"),
                    applicability_note=item.get("applicability_condition")
                )
                session.add(db_item)
            
            await session.commit()
            
        except Exception as e:
            logger.error(f"Error bootstrapping checklist from {p}: {e}")
            await session.rollback()
