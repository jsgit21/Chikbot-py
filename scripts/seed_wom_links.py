"""One-off backfill for the wom_link table.

Run separately against the database (NOT loaded by the bot). Reads a CSV with a
header row of: rsn,discord_user_id,alias  (alias optional per row).

    python scripts/seed_wom_links.py links.csv

Each RSN must already exist in wom_group (sync the group first) and each Discord
user must already exist in the `user` table (they exist once a member has chatted,
since chikbot registers users on message). Rows that fail either condition are
skipped and reported so they can be handled manually (e.g. via /wom link).
"""
import os
import sys
import csv
import argparse

import pymysql

# Allow running the file directly from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cogs.wise_old_man.identity import db as identity_db


def seed(csv_path):
    linked = 0
    skipped = []

    with open(csv_path, newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rsn = row['rsn'].strip()
            user_id = int(row['discord_user_id'].strip())
            alias = (row.get('alias') or '').strip()

            try:
                match = identity_db.link_rsn(rsn, user_id)
            except pymysql.err.IntegrityError:
                skipped.append((rsn, f'Discord user {user_id} not in `user` table'))
                continue

            if match is None:
                skipped.append((rsn, 'not found in wom_group'))
                continue

            if alias:
                identity_db.set_preferred_alias(user_id, alias)
            linked += 1

    print(f'Linked {linked} RSNs.')
    if skipped:
        print(f'Skipped {len(skipped)}:')
        for rsn, reason in skipped:
            print(f'  {rsn}: {reason}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Backfill wom_link from a CSV.')
    parser.add_argument('csv_path', help='Path to rsn,discord_user_id,alias CSV')
    args = parser.parse_args()
    seed(args.csv_path)
