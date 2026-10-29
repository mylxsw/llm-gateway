"""Versioned text estimator; metadata and serialized byte length are never billed."""
import re
from .validation import BillingError

ESTIMATOR_VERSION = 'unicode-v1'


def text_tokens(value):
    return sum((len(part)+2)//3 if part.isascii() else len(part)*2
               for part in re.findall(r'[\x00-\x7f]+|[^\x00-\x7f]+', value))


def estimate_input(body):
    messages = body.get('messages')
    system = body.get('system', '')
    if (not isinstance(messages, list) or not isinstance(system, str) or body.get('tools')
        or any(not isinstance(m, dict) or not isinstance(m.get('content'), str) for m in messages)):
        raise BillingError('unsupported_billing_input', 400)
    # tiktoken is optional and belongs to the gateway. Unknown models use this
    # deterministic estimator instead of silently selecting a generic tokenizer.
    try:
        import tiktoken
        encoding = tiktoken.encoding_for_model(body.get('model', ''))
    except (ImportError, KeyError):
        count, version = text_tokens, ESTIMATOR_VERSION
    else:
        count = lambda s: len(encoding.encode(s, disallowed_special=()))
        version = 'tiktoken-' + encoding.name
    total = 32 + sum(16 + count(m['content']) for m in messages) + count(system)
    return (total*120+99)//100, version
