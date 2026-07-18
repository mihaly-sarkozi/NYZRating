# Frontend Permissions

The frontend uses role-based route permissions in `frontend/src/platform/permissions.ts`.

## Roles

- `owner`: has `*`, so every frontend permission is granted.
- `admin`: can manage users and read/write settings.
- `user`: authenticated baseline only (login/refresh/logout); no admin-area permissions.

## Permission Map

- `users.read`, `users.write`, `users.invite`: `owner`, `admin`
- `settings.read`, `settings.write`: `owner`, `admin`
- `domain.read`, `domain.write`: `owner`, `admin`

## Route Requirements

- `/admin/roles`: `users.write`
- `/admin/settings`: `settings.read`

`ProtectedRoute` redirects unauthenticated users to `/login` with a safe internal redirect. Authenticated users without the required permission see the shared access denied state instead of the protected page.

Ha egy jövőbeli app-modul saját route-ot regisztrál `requiredPermission`-nel, a hozzá tartozó permission kulcsot itt, a `rolePermissions` térképben is fel kell venni a megfelelő szerepkörökhöz.
