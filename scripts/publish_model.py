"""Stage an exact original-format model early; upload only with an explicit --upload.
Uses existing HF authentication without ever printing a token. No new accounts.
"""
import argparse
import shutil
from pathlib import Path
from huggingface_hub import HfApi,snapshot_download

p=argparse.ArgumentParser()
p.add_argument('--repo',required=True,help='User-selected public account/name')
p.add_argument('--upload',action='store_true')
args=p.parse_args()
target=Path('models/hf-staging')
snapshot_download('Qwen/Qwen3.5-2B',revision='15852e8c16360a2fea060d615a32b45270f8a8fc',local_dir=target,ignore_patterns=['*.gguf'])
shutil.copyfile('hf-release/README.md',target/'README.md')
if args.upload:
    api=HfApi()
    print('Authenticated public identity:',api.whoami()['name'])
    api.create_repo(args.repo,repo_type='model',private=False,exist_ok=True)
    api.upload_folder(repo_id=args.repo,folder_path=target,commit_message='Publish pinned GeoLens base model, model card and upstream licence')
    print('Published:',args.repo)
else:
    print('Original-format model staged locally. Upload was not requested.')
