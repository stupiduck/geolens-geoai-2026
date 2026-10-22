"""Run in a separate release-verification environment with torch and transformers.
CPU original weights need more RAM than quantized production inference.
"""
import argparse
import json
import time
from pathlib import Path
import torch
from transformers import AutoProcessor,AutoModelForImageTextToText
p=argparse.ArgumentParser()
p.add_argument('--repo',required=True)
p.add_argument('--revision')
p.add_argument('--local-only',action='store_true')
p.add_argument('--output',default='docs/hf-load-verification.json')
args=p.parse_args()
torch.set_num_threads(2)
start=time.perf_counter()
processor=AutoProcessor.from_pretrained(args.repo,revision=args.revision,trust_remote_code=False,local_files_only=args.local_only)
model=AutoModelForImageTextToText.from_pretrained(args.repo,revision=args.revision,trust_remote_code=False,local_files_only=args.local_only,dtype='auto')
inputs=processor.apply_chat_template([{'role':'user','content':[{'type':'text','text':'Reply with one sentence about comparing two supplied weather forecasts.'}]}],tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True,enable_thinking=False)
with torch.inference_mode():
    output=model.generate(**inputs,max_new_tokens=16,do_sample=False)
report={'repo':args.repo,'revision':args.revision,'local_files_only':args.local_only,'parameters_loaded':sum(p.numel() for p in model.parameters()),'elapsed_seconds':round(time.perf_counter()-start,3),'output':processor.decode(output[0][inputs['input_ids'].shape[-1]:],skip_special_tokens=True)}
Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
