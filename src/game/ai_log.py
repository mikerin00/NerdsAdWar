# Module: ai_log
# AI decision log — records all reasoning for in-game review and file export
# Deduplicates repeated messages: "PULLBACK x3" instead of 3 separate entries

_entries  = []
_frameRef = [0]


def aiLogSetFrame(frame):
    _frameRef[0] = frame


def aiLog(msg):
    """Record an AI decision. Consecutive duplicates are collapsed into one entry."""
    frame = _frameRef[0]
    if _entries:
        prevFrame, prevMsg, prevCount = _entries[-1]
        if prevMsg == msg and frame - prevFrame < 300:
            _entries[-1] = (frame, msg, prevCount + 1)
            return
    _entries.append((frame, msg, 1))


def aiLogRecent(n=16):
    """Return the last n log entries as (frame, msg) tuples with count suffix."""
    result = []
    for frame, msg, count in _entries[-n:]:
        if count > 1:
            result.append((frame, f"{msg} (x{count})"))
        else:
            result.append((frame, msg))
    return result


def aiLogWrite(path='ai_log.txt'):
    """Write the full log to a text file."""
    with open(path, 'w', encoding='utf-8') as f:
        f.write("Nerds at War — AI Decision Log\n")
        f.write("=" * 50 + "\n\n")
        for frame, msg, count in _entries:
            secs = frame / 60
            suffix = f"  (x{count})" if count > 1 else ""
            f.write(f"[{secs:7.1f}s  f{frame:>5}]  {msg}{suffix}\n")
        f.write(f"\nTotal entries: {len(_entries)}\n")
