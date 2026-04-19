# 🌐 COMPLETE URL REFERENCE GUIDE

## All New Routes & Endpoints

---

## 📋 GROUP MANAGEMENT URLs

### 1. Edit Group
**URL Pattern**: `/group/<group_id>/edit/`
**Methods**: GET, POST
**Access**: Admin only
**Parameters**: group_id (integer)
**Template**: `edit_group.html`
**View Function**: `edit_group(request, group_id)`

**Usage**:
```
GET  /group/1/edit/          → Display edit form
POST /group/1/edit/          → Update group details
```

**Form Fields**:
- name (required)
- description (optional)
- category (required)

**Response**: Updated group with activity log entry

---

### 2. Delete/Archive Group
**URL Pattern**: `/group/<group_id>/delete/`
**Method**: POST
**Access**: Admin only
**Parameters**: group_id (integer)
**Template**: `delete_group_confirm.html`
**View Function**: `delete_group(request, group_id)`

**Usage**:
```
GET  /group/1/delete/        → Display confirmation
POST /group/1/delete/        → Archive/restore group
```

**Form Fields**:
- action (required: "archive" or "restore")

**Response**: Group archived/restored, activity logged

---

### 3. Transfer Ownership
**URL Pattern**: `/group/<group_id>/transfer-ownership/`
**Methods**: GET, POST
**Access**: Admin only
**Parameters**: group_id (integer)
**Template**: `transfer_ownership.html`
**View Function**: `transfer_ownership(request, group_id)`

**Usage**:
```
GET  /group/1/transfer-ownership/    → Display member list
POST /group/1/transfer-ownership/    → Transfer admin rights
```

**Form Fields**:
- new_admin_id (required: user ID)

**Response**: 
- New admin gets email notification
- Activity logged
- Ownership transferred

---

## 👥 MEMBER MANAGEMENT URLs

### 4. Remove Member
**URL Pattern**: `/group/<group_id>/remove-member/<member_id>/`
**Methods**: GET, POST
**Access**: Admin only
**Parameters**: 
- group_id (integer)
- member_id (integer)
**Template**: `remove_member_confirm.html`
**View Function**: `remove_member(request, group_id, member_id)`

**Usage**:
```
GET  /group/1/remove-member/2/    → Display confirmation
POST /group/1/remove-member/2/    → Remove member
```

**Response**: 
- Member removed from group
- Email notification sent
- Activity logged
- Expenses preserved

---

## 🎫 INVITE LINK MANAGEMENT URLs

### 5. Generate Invite Link
**URL Pattern**: `/group/<group_id>/invite-link/`
**Methods**: GET, POST
**Access**: Admin only
**Parameters**: group_id (integer)
**Template**: `generate_invite_link.html`
**View Function**: `generate_invite_link(request, group_id)`

**Usage**:
```
GET  /group/1/invite-link/    → Display form & active links
POST /group/1/invite-link/    → Create new invite link
```

**Form Fields**:
- max_uses (optional: integer, 0 = unlimited)
- expires_in (optional: days until expiry)

**Response**: 
- InviteLink created with unique token
- Template displays link and usage info
- Copy button available

---

### 6. Join via Invite Link
**URL Pattern**: `/invite/<token>/join/`
**Method**: GET
**Access**: Public (but requires login)
**Parameters**: token (UUID string)
**View Function**: `join_group_via_link(request, token)`

**Usage**:
```
GET /invite/a1b2c3d4-e5f6-7g8h-9i0j-k1l2m3n4o5p6/join/
```

**Requirements**:
- User must be logged in
- Invite link must be active
- Max uses not exceeded
- Not expired (if set)

**Response**: 
- User added to group as member
- Used count incremented
- Activity logged
- Redirect to group detail page

---

### 7. Revoke Invite Link
**URL Pattern**: `/invite/<invite_id>/revoke/`
**Method**: GET or POST
**Access**: Admin only
**Parameters**: invite_id (integer)
**View Function**: `revoke_invite_link(request, invite_id)`

**Usage**:
```
GET  /invite/1/revoke/    → Confirm revocation
POST /invite/1/revoke/    → Deactivate link
```

**Response**: 
- InviteLink marked as inactive
- Link no longer works
- Activity logged

---

## 📊 ACTIVITY & INFORMATION URLs

### 8. View Group Activity Log
**URL Pattern**: `/group/<group_id>/activity/`
**Method**: GET
**Access**: Group members
**Parameters**: group_id (integer)
**Template**: `group_activity_log.html`
**View Function**: `group_activity_log(request, group_id)`
**Query Parameters**: 
- type (optional: "all", "member_added", "expense_added", etc.)

**Usage**:
```
GET /group/1/activity/              → All activities
GET /group/1/activity/?type=expense_added  → Filter by type
```

**Response**: 
- Timeline of all group activities
- Statistics dashboard
- Filter tabs
- Activity descriptions with user info

**Activity Types Displayed**:
- member_added: Member Added
- member_removed: Member Removed
- expense_added: Expense Added
- expense_edited: Expense Edited
- expense_deleted: Expense Deleted
- settlement: Settlement Completed
- group_edited: Group Edited
- ownership_transferred: Ownership Transferred

---

## 🔌 API ENDPOINTS (AJAX)

### 9. Get Group Members (AJAX)
**URL Pattern**: `/api/group/<group_id>/members/`
**Method**: GET
**Access**: Group members
**Content-Type**: application/json
**Parameters**: group_id (integer)
**View Function**: `get_group_members(request, group_id)`

**Usage**:
```javascript
fetch('/api/group/1/members/')
  .then(response => response.json())
  .then(data => console.log(data))
```

**Response** (JSON):
```json
{
  "members": [
    {
      "id": 1,
      "name": "John Doe",
      "email": "john@example.com",
      "is_admin": true,
      "role": "admin",
      "joined_at": "2024-01-15T10:30:00Z"
    },
    {
      "id": 2,
      "name": "Jane Smith",
      "email": "jane@example.com",
      "is_admin": false,
      "role": "member",
      "joined_at": "2024-01-20T14:45:00Z"
    }
  ],
  "count": 2
}
```

---

### 10. Get Group Details (AJAX)
**URL Pattern**: `/api/group/<group_id>/details/`
**Method**: GET
**Access**: Group members
**Content-Type**: application/json
**Parameters**: group_id (integer)
**View Function**: `get_group_details(request, group_id)`

**Usage**:
```javascript
fetch('/api/group/1/details/')
  .then(response => response.json())
  .then(data => console.log(data))
```

**Response** (JSON):
```json
{
  "group": {
    "id": 1,
    "name": "Weekend Trip",
    "description": "Expenses for our vacation",
    "category": "trip",
    "created_at": "2024-01-10T09:00:00Z",
    "is_archived": false
  },
  "stats": {
    "total_members": 2,
    "total_expenses": 5,
    "total_amount": 2500.50,
    "settled_amount": 1200.00,
    "unsettled_amount": 1300.50,
    "is_admin": true
  }
}
```

---

## 📱 FULL URL MAPPING TABLE

| Feature | Method | URL | View Function | Template |
|---------|--------|-----|---------------|----------|
| Edit Group | GET/POST | `/group/<id>/edit/` | edit_group | edit_group.html |
| Delete Group | GET/POST | `/group/<id>/delete/` | delete_group | delete_group_confirm.html |
| Transfer Ownership | GET/POST | `/group/<id>/transfer-ownership/` | transfer_ownership | transfer_ownership.html |
| Remove Member | GET/POST | `/group/<id>/remove-member/<mid>/` | remove_member | remove_member_confirm.html |
| Generate Link | GET/POST | `/group/<id>/invite-link/` | generate_invite_link | generate_invite_link.html |
| Join via Link | GET | `/invite/<token>/join/` | join_group_via_link | group_detail.html (redirect) |
| Revoke Link | GET/POST | `/invite/<id>/revoke/` | revoke_invite_link | (redirect) |
| Activity Log | GET | `/group/<id>/activity/` | group_activity_log | group_activity_log.html |
| Members API | GET | `/api/group/<id>/members/` | get_group_members | (JSON) |
| Details API | GET | `/api/group/<id>/details/` | get_group_details | (JSON) |

---

## 🧪 TESTING URLS

### Test Scenario 1: Complete Group Workflow
```
1. GET  /group/1/edit/              # Open edit form
2. POST /group/1/edit/              # Update group
3. GET  /group/1/invite-link/       # Generate invite
4. POST /group/1/invite-link/       # Create invite
5. GET  /invite/TOKEN/join/         # Accept invite (as different user)
6. GET  /group/1/activity/          # View activity
```

### Test Scenario 2: Member Management
```
1. GET  /group/1/remove-member/2/   # Confirm removal
2. POST /group/1/remove-member/2/   # Remove member
3. GET  /api/group/1/members/       # Verify removal
4. GET  /group/1/activity/          # See removal logged
```

### Test Scenario 3: Ownership Transfer
```
1. GET  /group/1/transfer-ownership/      # Select member
2. POST /group/1/transfer-ownership/      # Transfer
3. GET  /api/group/1/details/            # Verify new admin
4. GET  /group/1/activity/               # See transfer logged
```

### Test Scenario 4: Real-time Data
```
1. GET  /api/group/1/members/           # Get members
2. GET  /api/group/1/details/           # Get details
3. (Member adds expense)
4. GET  /api/group/1/details/           # Verify update
5. GET  /group/1/activity/              # See activity logged
```

---

## 🔐 PERMISSION MATRIX

| URL | Admin | Member | Viewer | Public |
|-----|-------|--------|--------|--------|
| `/group/<id>/edit/` | ✅ | ❌ | ❌ | ❌ |
| `/group/<id>/delete/` | ✅ | ❌ | ❌ | ❌ |
| `/group/<id>/transfer-ownership/` | ✅ | ❌ | ❌ | ❌ |
| `/group/<id>/remove-member/<mid>/` | ✅ | ❌ | ❌ | ❌ |
| `/group/<id>/invite-link/` | ✅ | ❌ | ❌ | ❌ |
| `/invite/<token>/join/` | ✅ | ✅ | ✅ | ❌* |
| `/invite/<id>/revoke/` | ✅ | ❌ | ❌ | ❌ |
| `/group/<id>/activity/` | ✅ | ✅ | ✅ | ❌ |
| `/api/group/<id>/members/` | ✅ | ✅ | ✅ | ❌ |
| `/api/group/<id>/details/` | ✅ | ✅ | ✅ | ❌ |

*Requires login but no group membership

---

## 📤 HTTP METHODS CHEAT SHEET

### GET Requests (Safe, Idempotent)
```
GET  /group/1/edit/              Show edit form
GET  /group/1/delete/            Show delete confirmation
GET  /group/1/transfer-ownership/ Show member selection
GET  /group/1/remove-member/2/   Show removal confirmation
GET  /group/1/invite-link/       Show invite form & links
GET  /invite/TOKEN/join/         Join group automatically
GET  /group/1/activity/          View activity timeline
GET  /api/group/1/members/       Get members JSON
GET  /api/group/1/details/       Get details JSON
```

### POST Requests (Non-idempotent, State-changing)
```
POST /group/1/edit/              Update group details
POST /group/1/delete/            Archive/restore group
POST /group/1/transfer-ownership/ Execute ownership transfer
POST /group/1/remove-member/2/   Execute member removal
POST /group/1/invite-link/       Create new invite
POST /invite/ID/revoke/          Deactivate invite
```

---

## 🔗 URL GENERATION IN TEMPLATES

### Django URL Tag Usage
```django
<!-- Edit group -->
{% url 'edit_group' group.id %}
→ /group/1/edit/

<!-- Delete group -->
{% url 'delete_group' group.id %}
→ /group/1/delete/

<!-- Transfer ownership -->
{% url 'transfer_ownership' group.id %}
→ /group/1/transfer-ownership/

<!-- Remove member -->
{% url 'remove_member' group.id member.id %}
→ /group/1/remove-member/2/

<!-- Generate invite -->
{% url 'generate_invite_link' group.id %}
→ /group/1/invite-link/

<!-- Join via invite -->
{% url 'join_group_via_link' invite.token %}
→ /invite/a1b2c3d4.../join/

<!-- Revoke invite -->
{% url 'revoke_invite_link' invite.id %}
→ /invite/1/revoke/

<!-- Activity log -->
{% url 'group_activity_log' group.id %}
→ /group/1/activity/

<!-- API endpoints -->
/api/group/{{ group.id }}/members/
/api/group/{{ group.id }}/details/
```

---

## 🚀 EXAMPLE API CALLS

### JavaScript Fetch Examples

#### Get Members List
```javascript
async function getMembers(groupId) {
  const response = await fetch(`/api/group/${groupId}/members/`);
  const data = await response.json();
  console.log(data.members);
  return data;
}

getMembers(1);
```

#### Get Group Details
```javascript
async function getGroupDetails(groupId) {
  const response = await fetch(`/api/group/${groupId}/details/`);
  const data = await response.json();
  console.log(data.stats);
  return data;
}

getGroupDetails(1);
```

#### Poll for Real-time Updates
```javascript
async function pollGroupUpdates(groupId, interval = 5000) {
  setInterval(async () => {
    const data = await fetch(`/api/group/${groupId}/details/`).then(r => r.json());
    console.log('Updated stats:', data.stats);
    // Update UI with new data
  }, interval);
}

pollGroupUpdates(1);
```

---

## 📞 TROUBLESHOOTING URLS

### Common Issues & Solutions

**Issue: 404 Not Found on new URL**
```
Solution: Ensure migrations are applied
$ python manage.py migrate
```

**Issue: 403 Permission Denied**
```
Solution: Verify user is admin of group
Check: is_admin flag in response
```

**Issue: 404 on /invite/TOKEN/join/**
```
Solution: Verify invite link is active and not expired
Check: is_active and expires_at fields
```

**Issue: API returns empty members list**
```
Solution: Verify group has members
Check: GroupMember table has entries
```

---

## 📊 RESPONSE STATUS CODES

| Status | Meaning | Common URL |
|--------|---------|-----------|
| 200 | Success | Any GET request |
| 201 | Created | POST creating resource |
| 302 | Redirect | After successful action |
| 400 | Bad Request | Invalid form data |
| 403 | Forbidden | Permission denied |
| 404 | Not Found | Invalid group/member |
| 500 | Error | Server error |

---

## 🎯 QUICK REFERENCE BOOKMARKS

### For Admins
- `/group/1/edit/` - Edit group
- `/group/1/invite-link/` - Create invite
- `/group/1/transfer-ownership/` - Transfer admin
- `/group/1/activity/` - View all activities

### For Members
- `/group/1/activity/` - View activities
- `/api/group/1/members/` - Get members
- `/api/group/1/details/` - Get details

### For Public
- `/invite/TOKEN/join/` - Join via link

---

**URL Reference Guide Complete! ✅**

Use this guide for:
- Testing new features
- API integration
- Debugging issues
- Understanding permission levels
- Development reference

---

*Last Updated: Current Session*
*Status: All 13 new URLs documented*
