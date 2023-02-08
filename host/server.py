import argparse
import traceback

from flask import Flask, jsonify, render_template, request, redirect
from flask_compress import Compress

import polymath
from polymath.config.json import JSON
from polymath.config.env import Env
from polymath import get_completion, get_max_tokens_for_completion_model

DEFAULT_TOKEN_COUNT = 1000
answer_length = 512
# TODO: we need to allow room for the actual prompt, as well as separators
# between bits. This is a hand-tuned margin, but it should be calculated
# automatically.
context_count = get_max_tokens_for_completion_model() - 500 - answer_length

app = Flask(__name__)
Compress(app)

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
        # return 400 if no query is passed
        if 'query' not in args or not args['query'].strip() or len(args['query'].strip()) < 10:
            return jsonify({
                "error": "Missing or invalid 'query' parameter. Must be at least 10 characters."
            }), 400
        query = args['query'].strip()

        response_format = args.get('format', 'text')
        formatstring = ""
        formatcode = ""
        if response_format == 'markdown':
            formatstring = " in Markdown"
            formatcode = " If the question includes a request for code, provide a code block directly from the context."

        query_embedding = polymath.get_embedding(query)
        self.library.compute_similarities(query_embedding)
        self.library.sort = 'similarity'
        sliced_library = self.library.slice(context_count)
        sources = [{"url": info.url, "title": info.title} for info in sliced_library.unique_infos]
        context = sliced_library.text
        
        prompt = f"You are the \"WP Docs Bot\" created by Aaron Edwards (@UglyRobotDev) of Imajinn AI. Answer the question as truthfully as possible using the provided context, and if the answer is not contained within the text below, say \"I'm not sure\" and suggest looking for this information on https://wordpress.org.{formatcode}\n\nContext:\n{context} \n\nQuestion:\n{query}\n\nAnswer{formatstring}:"
        result = get_completion(prompt, answer_length=answer_length)
        return jsonify({"answer": result, "sources": sources})


@app.route("/", methods=["POST"])
def index():
    try:
        endpoint = Endpoint(library)
        return endpoint.query({
            'count': DEFAULT_TOKEN_COUNT,
            **request.form.to_dict()
        })

    except Exception as e:
        return jsonify({
            "error": f"{e}\n{traceback.format_exc()}"
        })


@app.route("/", methods=["GET"])
def render_index():
    #return render_template("query.html", config=host_config)
    return redirect("https://chatwp.imajinn.ai", code=302)


@app.route("/ask", methods=["POST"])
def ask():
    try:
        endpoint = Endpoint(library)
        return endpoint.ask({
            **request.form.to_dict()
        })

    except Exception as e:
        return jsonify({
            "error": f"{e}\n{traceback.format_exc()}"
        })

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port', help='Number of the port to run the server on (8080 by default).', default=8080, type=int)
    args = parser.parse_args()
    app.run(host='127.0.0.1', port=args.port, debug=True)
