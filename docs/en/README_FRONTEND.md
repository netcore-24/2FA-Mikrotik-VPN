# Frontend — MikroTik 2FA VPN System

Full-featured React 18 admin web UI.

## Tech stack

- **React 18** — UI library
- **Vite** — bundler & dev server
- **React Router** — routing
- **React Query (@tanstack/react-query)** — server state management
- **Zustand** — local state management (auth)
- **Axios** — HTTP client
- **CSS Modules** — styling

## Structure

```
frontend/
├── src/
│   ├── components/              # Reusable components
│   │   ├── Layout.jsx           # Main layout with navigation
│   │   ├── ProtectedRoute.jsx   # Route protection
│   │   ├── Modal.jsx            # Reusable modal component
│   │   └── Modal.css            # Modal styles
│   ├── pages/                   # App pages
│   │   ├── LoginPage.jsx
│   │   ├── DashboardPage.jsx
│   │   ├── UsersPage.jsx
│   │   ├── RegistrationRequestsPage.jsx
│   │   ├── VPNSessionsPage.jsx
│   │   ├── MikroTikPage.jsx
│   │   ├── StatsPage.jsx
│   │   ├── AuditLogsPage.jsx
│   │   └── SettingsPage.jsx
│   ├── services/                # API services
│   │   └── api.js               # Axios client with interceptors
│   ├── store/                   # Zustand stores
│   │   └── authStore.js
│   ├── App.jsx                  # Root component
│   └── main.jsx                 # Entry point
├── package.json
├── vite.config.js
└── index.html
```

## Install & run

### Development

```bash
cd frontend
npm install
npm run dev
```

The app will be available at `http://localhost:5173`.

### Production build

```bash
cd frontend
npm install
npm run build
```

Build artifacts will be in `dist/`. FastAPI will serve them automatically if the `dist` directory exists.

## Implemented pages

### 1) LoginPage (`/login`)
- Admin authentication
- Field validation
- Error handling
- Token persistence in localStorage

### 2) DashboardPage (`/`)
- System overview statistics (auto-refresh every 30 seconds)
- Key metric cards
- Quick actions (links to primary pages)

### 3) UsersPage (`/users`)
- Users table
- Search by name or Telegram ID
- Status filtering
- Edit modal (name, phone, email, status)
- Quick status toggles
- Pagination
- Colored status indicators

### 4) RegistrationRequestsPage (`/registration-requests`)
- Registration requests list
- Status filtering
- Approve/reject actions
- Rejection reason modal
- Display rejection reasons for rejected requests
- Pagination

### 5) VPNSessionsPage (`/vpn-sessions`)
- VPN sessions list
- Status filtering
- Disconnect sessions
- Extend session modal (select hours)
- Created/expiry timestamps
- Pagination

### 6) MikroTikPage (`/mikrotik`)
- Tabs:
  - **Configs** — MikroTik configs list, connection tests
  - **Users** — MikroTik User Manager users list, delete actions
  - **Firewall rules** — list and enable/disable actions
- Manual refresh button

### 7) StatsPage (`/stats`)
- Overview statistics
- User stats
- VPN session stats
- Registration request stats
- Cards and tables

### 8) AuditLogsPage (`/audit-logs`)
- Audit log list
- Filtering by action/entity type
- Details viewer (JSON)
- Pagination

### 9) SettingsPage (`/settings`)
- System settings list
- Category filtering
- Inline value editing
- JSON value support
- Delete settings (super-admin only)
- Encrypted value indicators

## Implementation notes

### Components
- **Modal** — reusable modal component for operations and confirmations
- **ProtectedRoute** — route guard for unauthenticated users
- **Layout** — main layout with navigation and header

### State management
- **React Query** for API requests + caching/refresh
- **Zustand** for auth state (token/admin)
- **useState** for local component state

### UX improvements
- Modals for edit/confirm flows
- Search & filters across list pages
- Form validation before submit
- Loading indicators for operations
- User-friendly error messages

### Auth
- JWT tokens in localStorage
- Auto refresh via interceptors
- Protected routes
- Redirect to `/login` when unauthenticated

## Backend integration

Pages are integrated with these API endpoints:
- `/api/auth/*`
- `/api/users/*`
- `/api/registration-requests/*`
- `/api/vpn-sessions/*`
- `/api/mikrotik/*`
- `/api/stats/*`
- `/api/audit-logs/*`
- `/api/settings/*`

## Styling

CSS variables are used for theming:
- `--primary-color`
- `--bg-color`
- `--card-bg`
- `--text-primary`
- `--border-color`

You can customize them in `index.css`.

## Security

- Tokens stored in localStorage
- Token refresh
- Auth checks on each request
- Protected routes
- CORS configured on backend

## Performance

- React Query caches requests
- Automatic cache invalidation after mutations
- Optimistic UI updates
- Lazy data loading (requests only when needed)

---

**All pages are functional and ready to use.**

