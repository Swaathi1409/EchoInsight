# EchoInsight Seed Coverage Matrix

This matrix maps every frontend page to its required API endpoints, database tables, feature flags, and settings. It determines what must be included in the deployment seed so that the application functions identically to local development.

| Frontend Page / Route | API Endpoints | Source Tables | Feature Flags | Jobs / Caches Needed | Settings Read | Seed Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Login** (`/login`) | `POST /api/v1/auth/login`, `GET /api/v1/auth/me` | `users` | None | None | `SECRET_KEY` | Users excluded from seed; admin created from ENV at boot |
| **Overview** (`/`) | `GET /api/v1/metrics/overview`, `GET /api/v1/conversations` | `conversations`, `analyses` | None | None | None | Served from seed directly |
| **Conversations** (`/conversations`) | `GET /api/v1/conversations` | `conversations`, `analyses`, `agents`, `teams` | None | None | None | Served from seed directly |
| **Conversation Detail** (`/conversations/:id`) | `GET /api/v1/conversations/:id`, `GET /api/v1/conversations/:id/turns` | `conversations`, `turns`, `analyses`, `qa_results`, `commitments` | None | Analytics extraction job | Taxonomy | Served from seed directly |
| **Quality** (`/quality`) | `GET /api/v1/metrics/quality`, `GET /api/v1/conversations` | `qa_results`, `conversations` | None | None | None | Served from seed directly |
| **Checklists** (`/checklists`) | `GET /api/v1/qa/checklists` | `qa_checklist`, `qa_checklist_version`, `qa_checklist_item` | None | None | Active checklist version | Settings seeded |
| **Commitments** (`/commitments`) | `GET /api/v1/commitments` | `commitments` | None | Commitments extraction | None | Served from seed directly |
| **Cases** (`/cases`) | `GET /api/v1/cases` | `cases`, `case_conversations` | None | Cases extraction | None | Needs derived tables seeded |
| **Recovery Desk** (`/action/recovery`) | `GET /api/v1/action/items` | `act_items`, `act_item_events`, `act_recommendations` | `ACTION_LAYER_ENABLED` | Action layer pipeline | `act_settings` | Needs flag and derived tables |
| **Recurring Issues** (`/action/recurring`) | `GET /api/v1/action/issues` | `act_recurring_issues`, `act_prevention_suggestions` | `ACTION_LAYER_ENABLED` | Derivation pipeline | None | Needs flag and derived tables |
| **Initiatives** (`/action/initiatives`) | `GET /api/v1/action/initiatives` | `act_initiatives`, `act_initiative_events` | `ACTION_LAYER_ENABLED` | User created / derived | None | Needs flag and derived tables |
| **Agents** (`/action/agents`) | `GET /api/v1/analytics/agents` | `agents`, `conversations`, `analyses` | `ACTION_LAYER_ENABLED` | Agent analytics rollup | None | Needs flag and derived tables |
| **Admin Settings** (`/admin`) | `GET /api/v1/config/settings` | `users` | None | None | ENV settings | Handled via ENV |
