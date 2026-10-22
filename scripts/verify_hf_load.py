"""Run in a separate release-verification environment with torch and transformers.
CPU original weights need more RAM than quantized production inference.
"""
import argparse
import json
from transformers import AutoProcessor,AutoModelForImageTextToText
p=argparse.ArgumentParser()
p.add_argument('--repo',required=True)
p.add_argument('--revision',required=True)
args=p.parse_args()
processor=AutoProcessor.from_pretrained(args.repo,revision=args.revision,trust_remote_code=False)
model=AutoModelForImageTextToText.from_pretrained(args.repo,revision=args.revision,trust_remote_code=False)
inputs=processor.apply_chat_template([{'role':'user','content':[{'type':'text','text':'Reply with one sentence about comparing two supplied weather forecasts.'}]}],tokenize=True,add_generation_prompt=True,return_tensors='pt',return_dict=True,enable_thinking=False)
output=model.generate(**inputs,max_new_tokens=40)
print(json.dumps({'repo':args.repo,'revision':args.revision,'parameters':sum(p.numel() for p in model.parameters()),'output':processor.decode(output[0][inputs['input_ids'].shape[-1]:],skip_special_tokens=True)},ensure_ascii=False))
