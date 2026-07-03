# Venue group mapping for migration 002
# representative: first spot id in each group (address/region source)

GROUPS = [
    {
        "name": "인제엑스게임리조트",
        "spot_ids": [261, 265, 68],
        "representative_id": 261,
    },
    {
        "name": "하동알프스레포츠(금오산)",
        "spot_ids": [262, 53],
        "representative_id": 262,
    },
    {
        "name": "제천청풍랜드",
        "spot_ids": [72, 263],
        "representative_id": 72,
    },
    {
        "name": "대천짚트랙타워",
        "spot_ids": [271, 273, 272],
        "representative_id": 271,
    },
    {
        "name": "단양만천하스카이워크",
        "spot_ids": [17, 20, 23, 25, 57],
        "representative_id": 17,
    },
    {
        "name": "해남땅끝마을스카이워크",
        "spot_ids": [21, 26],
        "representative_id": 21,
    },
    {
        "name": "거제바람의(도장포)",
        "spot_ids": [241, 259],
        "representative_id": 241,
    },
]

BACKUP_SUFFIX = ".backup_pre_venue_data"
MIGRATION_NAME = "002_map_venues"
