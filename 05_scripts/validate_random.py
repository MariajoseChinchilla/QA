#!/usr/bin/env python3
import argparse, csv
from collections import defaultdict

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidates', required=True)
    ap.add_argument('--responses', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--score', required=True)
    args=ap.parse_args()
    valid=defaultdict(set); meta={}
    with open(args.candidates, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            key=(r['case_id'], r['candidate_cod_cn_actual'], r['candidate_cod_abf_actual'])
            valid[r['case_id']].add((r['candidate_cod_cn_actual'], r['candidate_cod_abf_actual']))
            meta[r['case_id']]=r['expanded_route_id']
    rows=[]; score=defaultdict(lambda:{'valid':0,'invalid':0,'pending':0})
    with open(args.responses, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            cid=r['case_id']; route=r.get('expanded_route_id') or meta.get(cid,'')
            cn=(r.get('actual_cod_cn_actual') or '').strip(); abf=(r.get('actual_cod_abf_actual') or '').strip()
            if not cn and not abf:
                status='PENDING'; score[route]['pending']+=1
            elif (cn,abf) in valid.get(cid,set()):
                status='PASS_ACCEPTED_SET'; score[route]['valid']+=1
            else:
                status='FAIL_RANDOM_NOT_IN_ACCEPTED_SET'; score[route]['invalid']+=1
            out=dict(r); out['random_validation_status']=status; rows.append(out)
    fields=list(rows[0].keys()) if rows else ['case_id','random_validation_status']
    with open(args.out,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    with open(args.score,'w',newline='',encoding='utf-8') as f:
        fields=['expanded_route_id','actual_correct_count','invalid_random_selection_count','pending_count','branch_status']
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for route,s in sorted(score.items()):
            branch_status='PASS' if s['valid']==100 and s['invalid']==0 and s['pending']==0 else 'REVIEW'
            w.writerow({'expanded_route_id':route,'actual_correct_count':s['valid'],'invalid_random_selection_count':s['invalid'],'pending_count':s['pending'],'branch_status':branch_status})
if __name__=='__main__': main()
