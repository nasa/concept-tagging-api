import json
import logging
import os
from pathlib import Path

import dsconcept.get_metrics as gm
import joblib
import yaml
from flask import request, jsonify, render_template, Flask

logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.INFO)

app = Flask(__name__)
app.config["MODELS_DIR"] = os.environ["MODELS_DIR"]
LOG.info(f"Using MODELS_DIR \"{app.config['MODELS_DIR']}\"")

FIND_TERMS_METHOD_NAME = "findterms"
ALLOWED_FIND_TERMS_FIELDS = [
    "text",
    "probability_threshold",
    "topic_threshold",
    "request_id",
]

SERVICE_VERSION = os.environ["VERSION"] if "VERSION" in os.environ else "unspecified"
INTERFACE_VERSION = "2.0.0"
SERVICE_ROOT_PATH = ""

app.config.update(
    dict(
        CATEGORIES_DIR=f"{app.config['MODELS_DIR']}/categories/models",
        CONCEPTS_DIR=f"{app.config['MODELS_DIR']}/keywords/models",
        IN_KWD_RAW2LEMMA=f"{app.config['MODELS_DIR']}/kwd_raw2lemma.json",
        IN_CAT_RAW2LEMMA=f"{app.config['MODELS_DIR']}/cat_raw2lemma.json",
        IN_VECTORIZER=f"{app.config['MODELS_DIR']}/vectorizer.jbl",
        STI_CONFIG=f"{app.config['MODELS_DIR']}/config.yml",
        PRELOAD=False,  # TODO: visible configuration for preload option
        LOC_DICT=Path("loc_dict.jbl"),
    )
)


def load_models_wrapper():
    """
    If not preloading and mapping from (topic, keyword) to model paths already exists,
    just load it directly. Otherwise, load in all models and create the file.
    """
    if (not app.config['PRELOAD']) and (app.config['LOC_DICT'].exists()):
        cd = joblib.load(app.config['LOC_DICT'])
    elif not app.config['PRELOAD']:
        cd = gm.load_concept_models(app.config["CONCEPTS_DIR"],
                                    load=app.config['PRELOAD'])
        joblib.dump(cd, app.config['LOC_DICT'])
    else:
        cd = gm.load_concept_models(app.config["CONCEPTS_DIR"],
                                    load=app.config['PRELOAD'])
    return cd


def init():
    LOG.info("Loading lemma dictionaries.")
    with open(app.config["IN_KWD_RAW2LEMMA"], "r") as f0:
        app.config["KWD_RAW2LEMMA"] = json.load(f0)
    app.config["KWD_LEMMA2RAW"] = {v: k for k, v in app.config["KWD_RAW2LEMMA"].items()}

    with open(app.config["IN_CAT_RAW2LEMMA"], "r") as f0:
        app.config["CAT_RAW2LEMMA"] = json.load(f0)
    app.config["CAT_LEMMA2RAW"] = {v: k for k, v in app.config["CAT_RAW2LEMMA"].items()}

    with open(app.config["STI_CONFIG"], "r") as f0:
        cfg = yaml.safe_load(f0)
    weights = cfg["weights"]
    app.config["WEIGHTS"] = weights

    LOG.info("Loading hierarchical classifier.")
    cat_clfs = gm.load_category_models(app.config["CATEGORIES_DIR"])
    cd = load_models_wrapper()
    hclf = gm.HierarchicalClassifier(cat_clfs, cd)
    hclf.load_vectorizer(app.config["IN_VECTORIZER"])
    app.config["HIER_CLF"] = hclf
    LOG.info('Ready for requests.')


def classify_sti(texts, cat_threshold, kwd_threshold, no_categories):
    if type(texts) == str:
        texts = [texts]
    features, feature_matrix = app.config["HIER_CLF"].vectorize(
        texts, app.config["WEIGHTS"]
    )
    cat_preds, concept_preds = app.config["HIER_CLF"].predict(
        feature_matrix, cat_threshold, kwd_threshold, no_categories
    )
    cat_records = [
        [
            {
                "keyword": t[0],
                "probability": float(t[1]),
                "unstemmed": app.config["CAT_LEMMA2RAW"][t[0]],
            }
            for t in record_preds
        ]
        for record_preds in cat_preds
    ]
    concept_records = [
        [
            {
                "keyword": t[0],
                "probability": float(t[1]),
                "unstemmed": app.config["KWD_LEMMA2RAW"][t[0]],
            }
            for t in record_preds
        ]
        for record_preds in concept_preds
    ]
    if type(texts) == str:  # only return one if passed string instead of list
        LOG.info("Single example passed, returning single list.")
        features = features[0]
        cat_records = cat_records[0]
        concept_records = concept_records[0]
    return features, cat_records, concept_records


def _abort(code, msg, usage=True):
    if usage:
        msg += " " + _find_terms_usage() + "'"

    response = jsonify(service_version=SERVICE_VERSION, msg=msg)
    response.status_code = code
    return response


def _find_terms_usage(joinstr="', '", prestr="'"):
    return (
        "Allowed request fields for "
        + FIND_TERMS_METHOD_NAME
        + " method are "
        + prestr
        + joinstr.join(ALLOWED_FIND_TERMS_FIELDS)
    )


def _validate(data):
    for key in data:
        if key not in ALLOWED_FIND_TERMS_FIELDS:
            LOG.warning(f'"{key}" not in {ALLOWED_FIND_TERMS_FIELDS}')
            return False
    return True


@app.route(f"{SERVICE_ROOT_PATH}/")
def home():
    LOG.info(f"Loading page: {request.host}/{request.path}")
    if "HIER_CLF" not in app.config:
        init()
    return render_template(
        "home.html",
        version=SERVICE_VERSION,
        interface_version=INTERFACE_VERSION,
        root=SERVICE_ROOT_PATH,
        service_url=f"{request.host}/{request.path}",
        methodname=FIND_TERMS_METHOD_NAME,
        usage=_find_terms_usage(joinstr='", "', prestr='"') + '"',
    )


@app.route(f"{SERVICE_ROOT_PATH}/{FIND_TERMS_METHOD_NAME}/", methods=["POST"])
def find_terms():
    if "HIER_CLF" not in app.config:
        init()
    try:
        LOG.debug("Requesting information.")
        data = request.get_json(force=True)
        LOG.debug(f"Data received {str(data)}.")

        if not _validate(data):
            return _abort(400, "Bad Request incorrect field passed.")
        if "text" not in data:
            return _abort(400, "NO passed text field ..._abort.")
        else:
            text = data.get("text")
            if float(data.get("topic_threshold")) == 1.0:
                no_cats = True
            else:
                no_cats = False
            params = {
                "proba_lim": float(data.get("probability_threshold")),
                "topic_threshold": float(data.get("topic_threshold")),
                "request_id": str(data.get("request_id")),
                "no_categories": no_cats,
            }
        LOG.info(f'probability limit: {params["proba_lim"]}')
        LOG.info(f'request_id: {params["request_id"]}')
        features, cat_records, concept_records = classify_sti(
            text,
            params["topic_threshold"],
            params["proba_lim"],
            params["no_categories"],
        )
        payload = {
            "sti_keywords": concept_records,
            "features": features,
            "topic_probabilities": cat_records,
            "request_id": params["request_id"],
            "probability_threshold": params["proba_lim"],
            "topic_threshold": params["topic_threshold"],
        }
        LOG.info("Request Complete")
        return jsonify(
            status="okay",
            code=200,
            messages=[],
            service_version=SERVICE_VERSION,
            interface_version=INTERFACE_VERSION,
            payload=payload,
        )

    except Exception as ex:
        etype = type(ex)
        print(str(ex))

        if etype == ValueError or "BadRequest" in str(etype):
            return _abort(400, str(ex) + ".")
        else:
            print("Service Exception. Msg: " + str(type(ex)))
            return _abort(500, "Internal Service Error", usage=False)


if __name__ == "__main__":
    port = os.getenv("PORT")
    if port is None:
        LOG.info("Setting port to default value of 5000.")
        port = 5000
    app.run(
        host="0.0.0.0", port=int(port), threaded=True,
    )
