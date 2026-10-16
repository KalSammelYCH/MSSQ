"""独立提取判断和构造；输入采用回答，输出原值和证据。不读取Gold；两条个案判读及证据显式记录。"""
import json,re,hashlib
import joint_recovery as jr

def extract(e):
    """只接触回答文本和标签词表，不调用Gold、完整性检查或验证器。"""
    labels=e['manifest']['response_contract']['judgment_labels']
    field='schedule' if e['manifest']['family']=='scheduling' else 'assignment'
    pid=e['manifest']['prompt_id']
    # 对异常记录的已记录个案判读只裁决提交状态，不参考正确性。
    if e['model']=='Kimi-K2.6' and pid=='joint__scheduling__formal_csp0008__zh__may_witness':
        text=e['response'].get('reasoning_content') or e['stream_payload'][1] or ''
        phrase='答案：否。';start=text.rfind(phrase)
        assert start>=0 and '现在需要填写 reasoning_summary' in text[start:]
        return {'judgment':jr._normalize_judgment('否',labels),'construction':None,'construction_status':'missing',
            'method':'internal_component_review','ambiguity':False,'evidence':{'source':'reasoning_content','start':start,'end':start+len(phrase),'quote':phrase,'sha256':hashlib.sha256(text.encode()).hexdigest(),
                'reason':'末尾明确给出否定答案，随后仅总结论证，无再次撤回；不恢复早先被否定的排程。'}}
    if e['model']=='DeepSeek-V4-Pro' and pid=='joint__scheduling__formal_csp0005__zh__must_counterexample':
        text=e['response'].get('reasoning_content') or e['stream_payload'][1] or ''
        assert "I'll take one more chance" in text and 'Day3 afternoon' in text[-80:]
        return {'judgment':None,'construction':None,'construction_status':'withdrawn_or_unsettled','method':'internal_component_review','ambiguity':True,
            'evidence':{'source':'reasoning_content','sha256':hashlib.sha256(text.encode()).hexdigest(),'reason':'输出中的YES/null之后明确重新尝试相反方向并在搜索中截断；不能把此前候选当最终提交。'}}
    if e.get('adoption'):
        a=e['adoption']['answer_original_values']
        return {'judgment':jr._normalize_judgment(a['judgment'],labels),'construction':a.get(field),
            'construction_status':'null' if a.get(field) is None else 'value','method':'existing_explicit_adoption',
            'evidence':e['adoption'],'ambiguity':False}
    text=e['response'].get('response_text') or e['stream_payload'][0] or ''
    source='final_content'
    if not text.strip():
        reasoning=e['response'].get('reasoning_content') or e['stream_payload'][1] or ''
        markers=list(jr._FINAL_MARKER.finditer(reasoning))
        text='\n'.join(reasoning[m.end():markers[i+1].start() if i+1<len(markers) else len(reasoning)] for i,m in enumerate(markers))
        source='explicit_final_reasoning' if markers else 'no_final_answer'
    stripped=re.sub(r'^```(?:json)?\s*|\s*```$','',text.strip(),flags=re.I)
    whole=jr._parse_object(stripped)
    evidence=[];judgments=[];payloads=[];incomplete=False
    if whole is not None:
        for k in ['judgment','answer']:
            if k in whole:judgments.append(jr._normalize_judgment(whole[k],labels))
        if field in whole:payloads.append(whole[field])
        evidence=[{'source':source,'object':whole}]
        method='whole_final_object'
    else:
        decoder=json.JSONDecoder(object_pairs_hook=jr._object_no_duplicates)
        for match in re.finditer(r'"(judgment|answer|'+field+r')"\s*:\s*',text):
            k=match.group(1)
            try:value,end=decoder.raw_decode(text,match.end())
            except (ValueError,jr.DuplicateKeyError):
                if k==field:incomplete=True
                continue
            evidence.append({'source':source,'field':k,'start':match.end(),'end':end,'original_value':value})
            if k in ['judgment','answer']:judgments.append(jr._normalize_judgment(value,labels))
            else:payloads.append(value)
        method='explicit_fields' if evidence else source
        if not judgments:
            label=jr._normalize_judgment(re.sub(r'(?i)^judgment\s*[:：]?\s*','',stripped),labels)
            if label is not None:judgments=[label];method='bare_label'
    jset=set(judgments)
    unique={json.dumps(v,sort_keys=True,ensure_ascii=False):v for v in payloads}
    judgment=next(iter(jset)) if len(jset)==1 and None not in jset else None
    status='ambiguous' if len(unique)>1 else 'incomplete_syntax' if incomplete else 'missing'
    payload=None
    if len(unique)==1 and not incomplete:
        payload=next(iter(unique.values()));status='null' if payload is None else 'value'
    return {'judgment':judgment,'construction':payload,'construction_status':status,'method':method,
        'evidence':evidence,'ambiguity':len(jset)>1 or len(unique)>1,
        'judgment_candidates':judgments,'text_sha256':hashlib.sha256(text.encode()).hexdigest()}
