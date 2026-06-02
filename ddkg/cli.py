"""Command-line interface: `ddkg build`, `ddkg eval`, `ddkg stats`."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from .corpus import Corpus
from .pipeline import build_triples
from .builders import write_turtle, write_jsonld, write_cypher


def cmd_build(args: argparse.Namespace) -> int:
    corpus = Corpus(args.corpus)
    print(f"building KG from {corpus.root} …")
    triples, dd = build_triples(corpus, verbose=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n_ttl = write_turtle(triples, out / "gold.ttl")
    n_jld = write_jsonld(triples, out / "gold.jsonld")
    n_cy  = write_cypher(triples, out / "gold.cypher")
    print(f"built {len(triples)} triples from {len(dd.conflicts)} dropped conflicts:")
    print(f"  {out/'gold.ttl'}    ({n_ttl} graph statements)")
    print(f"  {out/'gold.jsonld'} ({n_jld} graph statements)")
    print(f"  {out/'gold.cypher'} ({n_cy} nodes+edges)")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    corpus = Corpus(args.corpus)
    triples, _ = build_triples(corpus)
    from collections import Counter
    from .model import NS
    typ = Counter(t.o for t in triples if t.p == NS.RDF + "type")
    print(f"corpus    : {corpus.root}")
    print(f"triples   : {len(triples)}")
    print(f"by rdf:type:")
    for k, v in typ.most_common():
        local = k.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
        print(f"  {v:>6}  {local}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from .eval import run_suite
    return run_suite(suite=args.suite, kg_path=args.kg, questions=args.questions)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ddkg",
                                 description="Knowledge-graph build & eval for dd-mockdata")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="extract a KG from a dd-mockdata corpus")
    p_build.add_argument("--corpus", default="../dd-mockdata",
                         help="path to dd-mockdata clone (default: ../dd-mockdata)")
    p_build.add_argument("--out", default="kg", help="output dir for gold.{ttl,jsonld,cypher}")
    p_build.set_defaults(func=cmd_build)

    p_stats = sub.add_parser("stats", help="print KG statistics")
    p_stats.add_argument("--corpus", default="../dd-mockdata")
    p_stats.set_defaults(func=cmd_stats)

    p_eval = sub.add_parser("eval", help="run an evaluation suite")
    p_eval.add_argument("--kg", default="kg/gold.ttl")
    p_eval.add_argument("--suite", choices=["ie", "rag", "contradiction"], required=True)
    p_eval.add_argument("--questions", default=None,
                        help="optional path to a questions JSON for the rag suite")
    p_eval.set_defaults(func=cmd_eval)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
