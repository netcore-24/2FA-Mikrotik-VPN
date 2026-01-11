# Database Management

Documentation for managing the SQLite database from the web UI.

## Download database

### Access
Settings → Database → Download backup

### Features
- Create a backup before downloading
- Download the `.db` file with current date/time in its name
- Optional compression to `.zip` or `.tar.gz`
- Log the operation to the audit log

### Security
- Super-admins only
- Permission checks before the operation

## Upload database

### Access
Settings → Database → Upload backup

### Process
1. Choose a `.db` file or an archive (`.zip`, `.tar.gz`)
2. Validate file format
3. Check database schema version (compatibility)
4. Create a backup of the current database
5. Warn about replacing the current database
6. Confirm the operation
7. Validate integrity of the uploaded database
8. Replace the current database
9. Optional service restart
10. Log the operation to the audit log

### Security
- Super-admins only
- Integrity checks before upload
- Automatic backup creation before operations
- Schema version validation

## Database information

### Displayed information
- Database file size
- Schema version
- Record count per table
- Last backup date
- Last modified date
- Disk usage statistics

### Access
Settings → Database → Info

## Automatic backups

### Configuration
- Backup interval (hours/days)
- Backup start time
- Retention policy (count/days)
- Backup storage path
- Backup compression
- Success/failure notifications

### Access
Settings → Database → Automatic backups

More details are described below in this document.

