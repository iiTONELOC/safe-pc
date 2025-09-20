import json
from multiprocessing import Process

from flask import Flask, request, make_response, jsonify

app = Flask(__name__)


@app.route("/api/answer_server", methods=["GET"])
def answer_server():
    # log some details about the  incoming request
    print("\nRequest Received:")
    print(json.dumps(request.headers, indent=4))
    return make_response(jsonify({"message": "Answer server is running"}), 200)


@app.route("/api/device_discovery", methods=["POST"])
def device_discovery():
    # print out the req body
    data = request.json
    print("\nDevice Discovery Data Received:")
    print(json.dumps(data, indent=4))
    return make_response(jsonify({"message": "Device discovery data received"}), 200)


def _start_server_new_process():
    p = Process(target=start_answer_server)
    p.start()
    return p


def start_answer_server():
    app.run(host="0.0.0.0", port=5000, debug=True)


def main():
    server_process = None
    try:
        server_process = _start_server_new_process()
        server_process.join()
    except KeyboardInterrupt:
        print("Shutting down the server.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if server_process:
            server_process.terminate()
            server_process.join()
        print("Server has been shut down.")


if __name__ == "__main__":
    main()
