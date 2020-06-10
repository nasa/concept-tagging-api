import argparse
import logging
from pathlib import Path
import json

import joblib
from tqdm import tqdm


logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

def get_dir_cons(mdir):
    cons = []
    for p in tqdm(mdir.iterdir()):
        c = joblib.load(p)['concept']
        cons.append(c)
    return cons


def main(model_dir, text_dir):
    LOG.info(f'Reading models from {model_dir}.')

    d = {
        'cat': model_dir / 'categories/models', 
        'kwd': model_dir / 'keywords/models/topic_',
    }
    for t, p in d.items():
        raw2lemma_loc = model_dir / f'{t}_raw2lemma.json'
        with open(raw2lemma_loc, 'r') as f0:
            raw2lemma = json.load(f0)
        lemma2raw = {v: k for k, v in raw2lemma.items()}
        tags = get_dir_cons(p)
        raw_tags = [lemma2raw[c] for c in tags]
        out_p = model_dir / f"{t}_list.txt"
        LOG.info(f'Writing {len(tags)} {t}s to {out_p}.')
        with open(out_p, 'w') as f0:
            for l in raw_tags:
                f0.write(l)
                f0.write('\n')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description = 'Make text files of all keyword tags from models.')
    parser.add_argument('--model_dir', help='input txt file', type=Path)
    parser.add_argument('--text_dir', help='input txt file', type=Path)
    args = parser.parse_args()
    main(args.model_dir, args.text_dir)
