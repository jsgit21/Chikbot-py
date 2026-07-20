def normalize_rsn(rsn):
    # wom_group stores display names lowercased, and OSRS dedupes hyphens vs spaces.
    return rsn.replace('-', ' ').lower()
