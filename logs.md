I've omitted the docker compose log output "instrumental-simple   | [simple] nothing to process" from the extract below since it presented quite frequently when there was nothing to process

instrumental-simple   | [simple] processing: /data/incoming/Alex Jean/Alex Jean - Kingdom Faith/03 - Life Has Changed.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Kingdom Faith/Life Has Changed.mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Alex Jean/Kingdom Faith/Life Has Changed.mp3
instrumental-simple   | [simple] processing: /data/incoming/Alex Jean/Alex Jean - Kingdom Faith/01 - Forever in Faith.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Kingdom Faith/Life Has Changed.mp3 (etag=f6262b4dd830bc39f04162434dba8431-2)
instrumental-simple   | [simple] done → /data/output/Alex Jean/Kingdom Faith/Forever in Faith.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Kingdom Faith/Forever in Faith.mp3 (etag=c057f5f5edbdbf6dc9844bcf56cd3f06-2)
instrumental-simple   | [simple] processing: /data/incoming/Alex Jean/Alex Jean - Kingdom Faith/02 - Back On The Road.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Kingdom Faith/Back On The Road.mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Alex Jean/Kingdom Faith/Back On The Road.mp3
instrumental-simple   | [simple] processing: /data/incoming/Alex Jean/Alex Jean - Kingdom Faith/04 - No Rolling Stones.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Kingdom Faith/Back On The Road.mp3 (etag=e5688a5013f1bc9d04e42d8882cf64e4)
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Kingdom Faith/No Rolling Stones.mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Alex Jean/Kingdom Faith/No Rolling Stones.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Kingdom Faith/No Rolling Stones.mp3 (etag=e7c77096f42acac44a214f895cf6d169-2)
instrumental-simple   | [simple] processing: /data/incoming/Alex Jean/Alex Jean - Stand Firm, You'll Win/01 - Stand Firm, You'll Win.mp3
instrumental-simple   | Traceback (most recent call last):
instrumental-simple   |   File "<frozen runpy>", line 198, in _run_module_as_main
instrumental-simple   |   File "<frozen runpy>", line 88, in _run_code
instrumental-simple   |   File "/app/app/main.py", line 19, in <module>
instrumental-simple   |     simple_main(sys.argv[2:])
instrumental-simple   |   File "/app/app/simple_runner.py", line 573, in main
instrumental-simple   |     progressed = process_one(cfg)
instrumental-simple   |                  ^^^^^^^^^^^^^^^^
instrumental-simple   |   File "/app/app/simple_runner.py", line 391, in process_one
instrumental-simple   |     duration = _ffprobe_duration_sec(src)
instrumental-simple   |                ^^^^^^^^^^^^^^^^^^^^^^^^^^
instrumental-simple   |   File "/app/app/simple_runner.py", line 249, in _ffprobe_duration_sec
instrumental-simple   |     return ffprobe_duration(p, cfg)
instrumental-simple   |            ^^^^^^^^^^^^^^^^^^^^^^^^
instrumental-simple   |   File "/app/app/audio.py", line 23, in ffprobe_duration
instrumental-simple   |     if p.returncode!=0: raise RuntimeError(p.stderr)
instrumental-simple   |                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
instrumental-simple   | RuntimeError: [mp3 @ 0x5684e6aac000] Failed to find two consecutive MPEG audio frames.
instrumental-simple   | /data/incoming/Alex Jean/Alex Jean - Stand Firm, You'll Win/01 - Stand Firm, You'll Win.mp3: Invalid data found when processing input
instrumental-simple   | 
instrumental-simple exited with code 1
instrumental-simple   | [simple] processing: /data/incoming/Alex Jean/Alex Jean - Stand Firm, You'll Win/01 - Stand Firm, You'll Win.mp3
instrumental-simple   | [simple] done → /data/output/Alex Jean/Stand Firm, You'll Win/Stand Firm, You'll Win.mp3
instrumental-simple   | [simple] processing: /data/incoming/Alex Jean/Alex Jean - Matthew 18_20/01 - Matthew 18_20.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Stand Firm, You'll Win/Stand Firm, You'll Win.mp3 (etag=15e0c2397c6167651037559cdcb2e024-2)
instrumental-simple   | [simple] done → /data/output/Alex Jean/Matthew 1820/Matthew 1820.mp3
instrumental-simple   | [simple] processing: /data/incoming/Sewa/Sewa - Holy/01 - Holy.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Alex Jean/Matthew 1820/Matthew 1820.mp3 (etag=3ff1050287c3faf02808281aad805e14-2)
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Holy/Holy.mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Sewa/Holy/Holy.mp3
instrumental-simple   | [simple] processing: /data/incoming/Sewa/Sewa - Holy Ghost/01 - Holy Ghost.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Holy/Holy.mp3 (etag=1e03492f173f0ec9f07abf3864035bd8-7)
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Holy Ghost/Holy Ghost.mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Sewa/Holy Ghost/Holy Ghost.mp3
instrumental-simple   | [simple] processing: /data/incoming/Sewa/Sewa - Give Me Oil/02 - Give Me Oil.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Holy Ghost/Holy Ghost.mp3 (etag=e88a178fe81d0380a43fa83598715014-7)
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Give Me Oil/Give Me Oil.mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Sewa/Give Me Oil/Give Me Oil.mp3
instrumental-simple   | [simple] processing: /data/incoming/Sewa/Sewa - Give Me Oil/01 - A Minister's Prayer.mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Give Me Oil/Give Me Oil.mp3 (etag=04932f7a24cbdae895512c7fde3435fe-5)
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Give Me Oil/A Minister's Prayer.mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Sewa/Give Me Oil/A Minister's Prayer.mp3
instrumental-simple   | [simple] processing: /data/incoming/Aware Worship/Aware Worship - So Glad You're Here/02 - Another Reason (Live).mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Sewa/Give Me Oil/A Minister's Prayer.mp3 (etag=2f6b9e904f54a4895066017be9a9b9fd)
minio-mirror          | [minio-mirror] uploaded: /data/output/Aware Worship/So Glad You're Here/Another Reason (Live).mp3 (etag=d41d8cd98f00b204e9800998ecf8427e)
instrumental-simple   | [simple] done → /data/output/Aware Worship/So Glad You're Here/Another Reason (Live).mp3
minio-mirror          | [minio-mirror] uploaded: /data/output/Aware Worship/So Glad You're Here/Another Reason (Live).mp3 (etag=4d1dea4f42ae7fa99e95b909fd774fbe-6)



pipeline-data/
├── archive
├── db
│   ├── mirror.sqlite
│   ├── mirror.sqlite-shm
│   ├── mirror.sqlite-wal
│   └── simple_runner.pid
├── filebrowser
│   ├── config
│   │   └── settings.json
│   └── database
│       └── filebrowser.db
├── incoming
├── incoming_queued
├── logs
│   └── simple_runner.jsonl
├── minio-data
│   └── instrumentals
│       ├── Alex Jean
│       │   ├── Kingdom Faith
│       │   │   ├── Back On The Road.mp3
│       │   │   │   ├── f2b8bdd3-adc7-4326-8347-546bedef98c0
│       │   │   │   │   └── part.1
│       │   │   │   └── xl.meta
│       │   │   ├── Forever in Faith.mp3
│       │   │   │   ├── ec410939-26cd-451b-b8e0-00de39d98111
│       │   │   │   │   ├── part.1
│       │   │   │   │   └── part.2
│       │   │   │   └── xl.meta
│       │   │   ├── Life Has Changed.mp3
│       │   │   │   ├── 7ce95581-fd55-4835-946e-17486afa00ef
│       │   │   │   │   ├── part.1
│       │   │   │   │   └── part.2
│       │   │   │   └── xl.meta
│       │   │   └── No Rolling Stones.mp3
│       │   │       ├── 97dbc968-e1e1-4839-a004-86b8879604ec
│       │   │       │   ├── part.1
│       │   │       │   └── part.2
│       │   │       └── xl.meta
│       │   ├── Matthew 1820
│       │   │   └── Matthew 1820.mp3
│       │   │       ├── edf6cae3-a4d9-4960-a178-f5df9ea958f7
│       │   │       │   ├── part.1
│       │   │       │   └── part.2
│       │   │       └── xl.meta
│       │   └── Stand Firm, You'll Win
│       │       └── Stand Firm, You'll Win.mp3
│       │           ├── 64a8d83d-bc6c-468f-bb92-397137696f39
│       │           │   ├── part.1
│       │           │   └── part.2
│       │           └── xl.meta
│       ├── Aware Worship
│       │   └── So Glad You're Here
│       │       └── Another Reason (Live).mp3
│       │           ├── 93ca345c-d350-4c40-b19b-89839190de4c
│       │           │   ├── part.1
│       │           │   ├── part.2
│       │           │   ├── part.3
│       │           │   ├── part.4
│       │           │   ├── part.5
│       │           │   └── part.6
│       │           └── xl.meta
│       ├── Madison Ryann Ward
│       │   └── A New Thing
│       │       ├── A New Thing.mp3
│       │       │   ├── ee525dc8-7c3c-4fb2-ad07-6afb7a67578b
│       │       │   │   ├── part.1
│       │       │   │   ├── part.2
│       │       │   │   └── part.3
│       │       │   └── xl.meta
│       │       ├── Chosen.mp3
│       │       │   ├── 2c175c83-22d1-43b9-9f08-740781595ecb
│       │       │   │   ├── part.1
│       │       │   │   └── part.2
│       │       │   └── xl.meta
│       │       ├── Go Back.mp3
│       │       │   ├── 9a6bea99-7f66-433f-8917-5ee37d9b8874
│       │       │   │   ├── part.1
│       │       │   │   └── part.2
│       │       │   └── xl.meta
│       │       └── You Love Me So.mp3
│       │           ├── e28e26a4-b01a-4302-aab6-922502248f20
│       │           │   ├── part.1
│       │           │   └── part.2
│       │           └── xl.meta
│       └── Sewa
│           ├── Give Me Oil
│           │   ├── A Minister's Prayer.mp3
│           │   │   ├── 72cd78db-907b-4fd2-8bbc-cf69467fd532
│           │   │   │   └── part.1
│           │   │   └── xl.meta
│           │   └── Give Me Oil.mp3
│           │       ├── 20943118-fad6-4871-8cef-b6b2db2046b9
│           │       │   ├── part.1
│           │       │   ├── part.2
│           │       │   ├── part.3
│           │       │   ├── part.4
│           │       │   └── part.5
│           │       └── xl.meta
│           ├── Holy
│           │   └── Holy.mp3
│           │       ├── cfe88bb7-a204-4250-8253-46a2d060e647
│           │       │   ├── part.1
│           │       │   ├── part.2
│           │       │   ├── part.3
│           │       │   ├── part.4
│           │       │   ├── part.5
│           │       │   ├── part.6
│           │       │   └── part.7
│           │       └── xl.meta
│           └── Holy Ghost
│               └── Holy Ghost.mp3
│                   ├── 08e0847e-d566-4936-b091-33a20c070cb2
│                   │   ├── part.1
│                   │   ├── part.2
│                   │   ├── part.3
│                   │   ├── part.4
│                   │   ├── part.5
│                   │   ├── part.6
│                   │   └── part.7
│                   └── xl.meta
├── models
│   └── torch
│       └── hub
│           └── checkpoints
│               └── 955717e8-8726e21a.th
├── output
│   ├── Alex Jean
│   │   ├── Kingdom Faith
│   │   │   ├── Back On The Road.mp3
│   │   │   ├── Forever in Faith.mp3
│   │   │   ├── Life Has Changed.mp3
│   │   │   └── No Rolling Stones.mp3
│   │   ├── Matthew 1820 (This album did not preserve the original name "Matthew 18:20")
│   │   │   └── Matthew 1820.mp3 (This song title did not preserve the original name "Matthew 18:20")
│   │   └── Stand Firm, You'll Win
│   │       └── Stand Firm, You'll Win.mp3
│   ├── Aware Worship
│   │   └── So Glad You're Here
│   │       └── Another Reason (Live).mp3
│   ├── Madison Ryann Ward
│   │   └── A New Thing
│   │       ├── A New Thing.mp3
│   │       ├── Chosen.mp3
│   │       ├── Go Back.mp3
│   │       └── You Love Me So.mp3
│   └── Sewa
│       ├── Give Me Oil
│       │   ├── A Minister's Prayer.mp3
│       │   └── Give Me Oil.mp3
│       ├── Holy
│       │   └── Holy.mp3
│       └── Holy Ghost
│           └── Holy Ghost.mp3
├── test
├── test-data
└── working
    └── simple_1755499406 (this seemed to be a leftover dir after the cleanup process ran)

Help me understand and fix the traceback error as well as ensure that the original names of Artists, Albums, and Song Titles are preserved when the metadata is being captured 