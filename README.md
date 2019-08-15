# tf-gcloud


virtualenv --python python3     ~/envs/tf-gcloud
source     ~/envs/tf-gcloud/bin/activate
pip install -r requirements.txt
python main.py
history
gcloud app deploy app.yaml \project linen-hook-248923
