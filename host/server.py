import argparse
import datetime
import hashlib
import traceback
import openai

from flask import Flask, jsonify, render_template, request, redirect
from flask_compress import Compress
from flask_cors import CORS

import polymath
from polymath.config.json import JSON
from polymath.config.env import Env
from polymath import get_completion, get_max_tokens_for_completion_model

from google.cloud import datastore
client = datastore.Client()

DEFAULT_TOKEN_COUNT = 2000  # get_max_tokens_for_completion_model()
answer_length = 256
PROMPT_LENGTH = 108  # with markdown arg
MAX_QUERY_LENGTH = 200  # characters not tokens
# We need to allow room for the actual prompt, as well as separators
# between bits. This is a hand-tuned margin, but it should be calculated
# automatically.
context_count = DEFAULT_TOKEN_COUNT - PROMPT_LENGTH - \
    (MAX_QUERY_LENGTH / 4) - answer_length

app = Flask(__name__)
Compress(app)
CORS(app)

env_config = Env.load_environment_config()
host_config = JSON.load_host_config()

library = polymath.load_libraries(env_config.library_filename, True)


class Endpoint:
    def __init__(self, library):
        self.library = library

    def query(self, args: dict[str, str]):
        result = self.library.query(args)
        return jsonify(result.serializable())

    # ask endpoint, passing in a query arg via POST
    def ask(self, args: dict[str, str]):
        # accept json or form data
        if request.is_json:
            args = request.get_json()

        # return 400 if no query is passed
        if 'query' not in args or not args['query'].strip() or len(args['query'].strip()) < 10 or len(args['query'].strip()) > MAX_QUERY_LENGTH:
            return jsonify({
                "error": f"Missing or invalid 'query' parameter. Must be between 10 and {MAX_QUERY_LENGTH} characters."
            }), 400
        query = args['query'].strip()

         # get their IP from the request, hash it, and store in datastore
        ip = request.headers.get('X-Appengine-User-IP', request.remote_addr)
        iphash = hashlib.sha256(ip.encode('utf-8')).hexdigest()

        openai_api_key = request.headers.get('x-openai-api-key', False)
        if openai_api_key and len(openai_api_key) > 20:
            openai.api_key = openai_api_key.strip()
        else:
            # get count of asks from this iphash in the last 24 hours
            dsquery = client.query(kind="Ask")
            dsquery.add_filter("iphash", "=", iphash)
            dsquery.add_filter("created", ">=", datetime.datetime.now(
                tz=datetime.timezone.utc) - datetime.timedelta(days=1))
            dsquery.keys_only()
            ask_count = len(list(dsquery.fetch()))
            if ask_count > 6:
                return jsonify({
                    "error": f"Too many requests. Please try again later or include your OpenAI API key."
                }), 429

        response_format = args.get('format', 'text')
        formatstring = ""
        formatcode = ""
        if response_format == 'markdown':
            formatstring = " in Markdown"
            formatcode = " If the question includes a request for code, provide a code block directly from the context."

        query_embedding = polymath.get_embedding(query, self.library.EMBEDDINGS_MODEL_ID, 1)
        if query_embedding is None:
            return jsonify({
                "error": f"OpenAI API key is invalid."
            }), 403

        self.library.compute_similarities(query_embedding)
        self.library.sort = 'similarity'
        sliced_library = self.library.slice(context_count)
        sources = [{"url": info.url, "title": info.title}
                   for info in sliced_library.unique_infos]
        context = sliced_library.text

        prompt = f"You are the \"ChatWP Bot\" created by Aaron Edwards (@UglyRobotDev). Answer the question as truthfully as possible using the provided context, and if the answer is not contained within the text below, say \"I'm not sure\" and suggest looking for this information on [wordpress.org](https://wordpress.org).{formatcode}\n\nContext:\n{context} \n\nQuestion:\n{query}\n\nAnswer{formatstring}:"
        result = get_completion(prompt, answer_length=answer_length)

        # Store iphash in google cloud datastore
        key = client.key("Ask")
        ask = datastore.Entity(key, exclude_from_indexes=("result","sources",))
        ask.update(
            {
                "created": datetime.datetime.now(tz=datetime.timezone.utc),
                "query": query,
                "iphash": iphash,
                "result": result,
                "sources": sources,
                "rating": 0,
            }
        )
        client.put(ask)

        return jsonify({"answer": result, "sources": sources, "id": ask.key.id})


@app.route("/", methods=["POST"])
def index():
    try:
        endpoint = Endpoint(library)
        return endpoint.query({
            'count': DEFAULT_TOKEN_COUNT,
            **request.form.to_dict()
        })

    except Exception as e:
        print(f"{e}\n{traceback.format_exc()}")
        return jsonify({
            "error": f"{e}"
        })


@app.route("/", methods=["GET"])
def render_index():
    # return render_template("query.html", config=host_config)
    return redirect("https://wpdocs.chat", code=302)


@app.route("/ask", methods=["POST"])
def ask():
    try:
        endpoint = Endpoint(library)
        return endpoint.ask({
            **request.form.to_dict()
        })

    except Exception as e:
        print(f"{e}\n{traceback.format_exc()}")
        return jsonify({
            "error": f"{e}"
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port', help='Number of the port to run the server on (8080 by default).', default=8080, type=int)
    args = parser.parse_args()
    app.run(host='127.0.0.1', port=args.port, debug=True)
