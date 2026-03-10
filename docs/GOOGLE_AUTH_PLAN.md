# Google Sign In + Drive Watchlist Plan

## Goal

Replace password-based authentication with Google Sign In, and store user's watchlist in their own Google Drive (App Data folder). The server stores **zero user data** — all personal data lives in the user's Google account.

## Architecture

```
User → Google Sign In (OAuth 2.0)
  → Frontend gets access_token + user info (email, name)
  → Frontend uses Google Drive API to read/write watchlist.json
  → Server only provides analysis tools, no user data stored
```

### Why This Architecture

- **Zero privacy risk**: Server never touches user's watchlist data
- **Cross-device sync**: User logs in on any device, watchlist follows
- **Auto-cleanup**: User revokes app access → data auto-deleted
- **Simple audit**: No user database = nothing to leak

## OAuth Scope

```
openid                          # Basic identity
email                           # Email address for display
profile                         # Name for display
https://www.googleapis.com/auth/drive.appdata  # Hidden app-specific folder
```

`drive.appdata` is the key — it only accesses a hidden folder specific to our app, cannot see any other files in the user's Drive.

## Data Schema

### watchlist.json (stored in user's Google Drive App Data)

```json
{
  "version": 1,
  "watchlist": [
    {
      "ticker": "CCJ",
      "name": "Cameco",
      "added_at": "2026-03-09T14:00:00Z"
    },
    {
      "ticker": "2330.TW",
      "name": "台積電",
      "added_at": "2026-03-09T14:00:00Z"
    }
  ],
  "settings": {
    "default_period": "3.5",
    "default_view": "fivelines"
  }
}
```

## Access Levels

| Login State | Features |
|---|---|
| Not logged in | 熱門分析, 指數ETF tabs + manual ticker input |
| Google Sign In | Above + 追蹤清單 (synced via Drive) + add/remove stocks |

## Implementation Steps

### Phase 1: Google Cloud Setup
1. Create OAuth 2.0 Client ID in Google Cloud Console
2. Enable Google Drive API
3. Configure consent screen (app name, scopes)
4. Authorized JavaScript origins: `https://stock.cwithb.com`
5. Store Client ID in Vercel env var: `GOOGLE_CLIENT_ID`

### Phase 2: Frontend — Google Sign In
1. Add Google Identity Services library (`accounts.google.com/gsi/client`)
2. Replace password gate with Google Sign In button
3. On sign-in success: store token in sessionStorage, show user name/avatar
4. Add sign-out button
5. Keep password gate as fallback (for non-Google users or testing)

### Phase 3: Frontend — Drive Watchlist
1. On sign-in: call Drive API to find `watchlist.json` in appDataFolder
2. If not found: create empty watchlist
3. Populate 追蹤清單 tab from watchlist data
4. Add "+" button on each stock analysis result to add to watchlist
5. Add "×" button on watchlist items to remove
6. On any change: write updated watchlist.json back to Drive

### Phase 4: Backend Changes
1. Add `GOOGLE_CLIENT_ID` env var
2. Expose client ID via `/api/config` endpoint (public, no secrets)
3. No other backend changes needed — all Drive operations happen client-side

### Phase 5: Testing
1. Unit tests for any new backend endpoints
2. Manual E2E testing: sign in → add stock → sign out → sign in again → verify persistence
3. Test on mobile browser
4. Test with multiple Google accounts

## API Calls (all client-side)

### Find watchlist file
```javascript
GET https://www.googleapis.com/drive/v3/files
  ?spaces=appDataFolder
  &q=name='watchlist.json'
  &fields=files(id)
Headers: Authorization: Bearer {access_token}
```

### Read watchlist
```javascript
GET https://www.googleapis.com/drive/v3/files/{fileId}
  ?alt=media
Headers: Authorization: Bearer {access_token}
```

### Create watchlist (first time)
```javascript
POST https://www.googleapis.com/upload/drive/v3/files
  ?uploadType=multipart
Body: metadata { name: 'watchlist.json', parents: ['appDataFolder'] }
      + JSON content
Headers: Authorization: Bearer {access_token}
```

### Update watchlist
```javascript
PATCH https://www.googleapis.com/upload/drive/v3/files/{fileId}
  ?uploadType=media
Body: JSON content
Headers: Authorization: Bearer {access_token}
```

## UI Changes

### Before Login
- Show Google Sign In button (replaces password input)
- 追蹤清單 tab locked with "登入 Google 解鎖" tooltip

### After Login
- Show user avatar + name in top-left of panel
- 追蹤清單 tab unlocked, populated from Drive
- Each analysis result has "加入追蹤" button
- Sign-out link in panel footer

## Security Considerations

- Access token only stored in sessionStorage (not localStorage) — cleared on tab close
- Token has limited scope (only appDataFolder, not full Drive)
- Server never sees or stores the access token
- Client ID is public (safe to expose, it's not a secret)
- No user data in our database = no data breach possible

## Rollback Plan

If Google auth has issues, the password gate (`ccj`/`2330`) remains as fallback. Both can coexist during migration.

## Timeline Estimate

- Phase 1 (GCP setup): Manual, ~15 min
- Phase 2 (Sign In): ~1 session
- Phase 3 (Drive): ~1 session
- Phase 4 (Backend): Minimal
- Phase 5 (Testing): ~30 min
