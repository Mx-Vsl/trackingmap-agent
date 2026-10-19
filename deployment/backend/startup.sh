#!/bin/bash
cd /home/site/wwwroot
python -m pip install -r requirements.txt
python -c "import trackingmap_agent.tracker_db; trackingmap_agent.tracker_db.init_db(use_azure_sql=True)"
