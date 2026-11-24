"""Display an explicit request from a stopped draft without certifying the draft."""
import re


def explicit_questions(report):
    # Mathematical output and its replay digest are not modified here. A model
    # may correctly say NOT_POINT and still explicitly request missing inputs.
    if (report.get('clarification_questions') or report.get('proof')
            or report.get('decision') != 'RETAINED'
            or report.get('estimation_handoff_allowed')):
        return []
    draft=report.get('effective_answer')
    if not isinstance(draft,dict):return []
    draft=draft.get('answer',draft)
    if not isinstance(draft,dict):return []
    parts=draft.get('answers',[draft])
    if not isinstance(parts,list):return []
    questions=[]
    for part in parts:
        if not isinstance(part,dict) or part.get('status') not in {'NEEDS_INPUT','NOT_POINT','NOT_COVERED','PARTIAL'}:
            continue
        handoff=part.get('estimate_handoff')
        if not isinstance(handoff,dict) or handoff.get('mode')!='STOP':continue
        reason=part.get('reason')
        if not isinstance(reason,str):continue
        # Extract only a complete, explicitly requested user action/question;
        # never turn a suggested scientific assumption into an approval.
        for sentence in re.findall(r'[^。！？\n]+[。！？]?',reason):
            sentence=sentence.strip()
            if len(sentence)<=500 and re.match(r'^请(?:问|提供|说明|确认是否|补充)',sentence):
                questions.append(sentence)
    return list(dict.fromkeys(questions))
