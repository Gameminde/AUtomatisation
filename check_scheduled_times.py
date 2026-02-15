"""Check scheduled times."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import config
from datetime import datetime, timezone

client = config.get_supabase_client()

# Get scheduled posts
scheduled = client.table('scheduled_posts').select('id, content_id, scheduled_time, status').eq('status', 'scheduled').order('scheduled_time').limit(10).execute()

now = datetime.now(timezone.utc)
print(f"Current UTC time: {now.isoformat()}")
print("\n=== Scheduled Posts ===")

for row in scheduled.data:
    scheduled_time = row.get('scheduled_time', '')
    sched_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00').replace('+00:00', ''))
    is_due = sched_dt <= now
    status = "DUE NOW" if is_due else f"in {(sched_dt - now).total_seconds() / 3600:.1f}h"
    print(f"{row['id'][:8]} | {scheduled_time} | {status}")
