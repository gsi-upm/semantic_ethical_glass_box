"""Characterise the captured real interaction (answers the open question).

Reports: number of POST /ttl per interaction, triples per payload, total
triples, and the real inter-log gaps. This is the 'demonstrated use' evidence
for the paper (a real interaction, real counts).
"""
import sys

from segb_bench.replay import count_triples, load_capture, real_gaps


def main(path: str = "capture.json") -> None:
    cap = load_capture(path)
    n = len(cap.payloads)
    triples = [count_triples(p["ttl"]) for p in cap.payloads]
    gaps = real_gaps(cap)[1:]
    print(f"capture file        : {path}")
    print(f"POST /ttl count     : {n}")
    print(f"total triples       : {sum(triples)}")
    print(f"triples per publish : min={min(triples)} max={max(triples)} "
          f"mean={sum(triples)/n:.1f}")
    if gaps:
        print(f"inter-log gap (s)   : min={min(gaps):.3f} max={max(gaps):.3f} "
              f"mean={sum(gaps)/len(gaps):.3f}")
    print(f"interaction span (s): {cap.payloads[-1]['ts'] - cap.payloads[0]['ts']:.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "capture.json")
