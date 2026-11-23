"""Local multi-attachment business intake -> grounded formulation (v0.7).

Examples:
 python -m cfm_id_llm.multisource_intake_cli --manifest examples/multisource/case.json --preview
 python -m cfm_id_llm.multisource_intake_cli --manifest examples/multisource/case.json --provider mock --mock-response examples/multisource/mock_draft.json

An external provider requires BOTH --allow-external and --allow-document-sharing.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from .document_intake import AttachmentRequestV07, AttachmentError, IntakeReportV07, create_intake
from .formulator import ProblemFormulator
from .multisource_normalization import SYSTEM_PROMPT_V07, PROMPT_VERSION_V07, review_intake, render_multisource_review
from .providers import MockProvider, OpenAICompatibleChatProvider, ProviderError
from .schemas import BusinessCase


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='CFM-ID Gateway v0.7: business narrative + local attachments -> grounded math draft')
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--manifest', help='JSON {case_id, business_question, attachments:[{path,kind}]}')
    group.add_argument('--question', help='business question in everyday language')
    p.add_argument('--case-id', default='business_with_documents')
    p.add_argument('--attachment', action='append', default=[], help='local file path; may repeat')
    p.add_argument('--provider', choices=('mock','openai-chat'), default='mock')
    p.add_argument('--mock-response', help='LLM DraftProblemSpec fixture, only for mock')
    p.add_argument('--model', help='online JSON-capable model')
    p.add_argument('--base-url', default='https://api.openai.com/v1')
    p.add_argument('--allow-external', action='store_true')
    p.add_argument('--allow-document-sharing', action='store_true', help='confirm textual excerpts and table schema can go to online provider')
    p.add_argument('--preview', action='store_true', help='only ingest local materials; no LLM')
    p.add_argument('--format', choices=('text','json'), default='text')
    p.add_argument('--output', help='write report to local path')
    p.add_argument('--case-output', help='save BusinessCase for future core-adapter or review')
    return p


def _load_manifest(path: Path) -> tuple[str, str, str, list[AttachmentRequestV07]]:
    raw = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(raw, dict) or not isinstance(raw.get('attachments'), list):
        raise ValueError('Invalid intake manifest')
    root = path.resolve().parent
    attachments = []
    for entry in raw['attachments']:
        item = AttachmentRequestV07.model_validate(entry)
        reference = Path(item.path)
        if reference.is_absolute() or '..' in reference.parts:
            raise AttachmentError('Manifest paths must be relative to manifest directory')
        resolved = (root / reference).resolve()
        if not resolved.is_relative_to(root):
            raise AttachmentError('Manifest attachment path escapes its folder')
        attachments.append(item.model_copy(update={'path': str(resolved)}))
    return raw['case_id'], raw['business_question'], raw.get('response_language', 'zh'), attachments


def main(argv: list[str] | None = None) -> int:
    p = parser()
    args = p.parse_args(argv)
    try:
        if args.manifest:
            case_id, question, language, attachments = _load_manifest(Path(args.manifest))
        else:
            case_id, question, language = args.case_id, args.question, 'zh'
            attachments = [AttachmentRequestV07(path=s) for s in args.attachment]
        # --attachment with manifest is disallowed to avoid silently ignoring user documents.
        if args.manifest and args.attachment:
            raise ValueError('Use only manifest attachments or --attachment paths, not both')
        intake = create_intake(case_id=case_id, business_question=question,
                               attachments=attachments, response_language=language)
        if args.case_output:
            Path(args.case_output).write_text(intake.case.model_dump_json(indent=2)+'\n', encoding='utf-8')
        if args.preview:
            result = intake.model_dump_json(indent=2) if args.format == 'json' else (
                f'已读取业务描述和 {len(intake.attachments)} 份附件；只生成后台材料包，尚未调用 LLM 或数学识别。\n'
                + '\n'.join(f'- {a.display_name}：{a.mode}; {a.bytes} bytes; 提取警告：{", ".join(a.warnings) or "无"}' for a in intake.attachments)
                + '\n表格仅汇总列名与行数；有限数据不能自行证明总体 A4。')
        else:
            if args.provider == 'mock':
                if not args.mock_response:
                    raise ValueError('Mock provider requires --mock-response')
                provider = MockProvider(json.loads(Path(args.mock_response).read_text(encoding='utf-8')))
            else:
                if not (args.allow_external and args.allow_document_sharing):
                    p.error('Online requests require BOTH --allow-external and --allow-document-sharing')
                if not args.model:
                    raise ValueError('Online requests require --model')
                provider = OpenAICompatibleChatProvider(model=args.model, base_url=args.base_url)
            form = ProblemFormulator(provider, system_prompt=SYSTEM_PROMPT_V07,
                                     prompt_version=PROMPT_VERSION_V07).formulate(intake.case)
            review = review_intake(intake, form)
            result = review.model_dump_json(indent=2) if args.format == 'json' else render_multisource_review(review)
        if args.output:
            Path(args.output).write_text(result + '\n', encoding='utf-8')
        else:
            try:
                print(result)
            except UnicodeEncodeError:
                # Respect redirected stdout's encoding; preserve every JSON string on round trip.
                if args.format == 'json':
                    print(json.dumps(json.loads(result), ensure_ascii=True, indent=2))
                else:
                    encoding = sys.stdout.encoding or 'utf-8'
                    print(result.encode(encoding, errors='backslashreplace').decode(encoding))
        return 0
    except (AttachmentError, OSError, ValueError, ProviderError, json.JSONDecodeError) as exc:
        # Avoid leaking private business payload / filenames / model response in errors.
        print(f'Document-aware normalization stopped safely ({type(exc).__name__}). Check files and consent.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
