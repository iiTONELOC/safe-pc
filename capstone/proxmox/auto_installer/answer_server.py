import json
from multiprocessing import Process
from capstone.proxmox.answer_file.utils import gen_ans_file_with

from flask import Flask, request, make_response, jsonify
import tempfile
from flask import send_file


app = Flask(__name__)

cached_answer_files = {}


# NOT SURE WHY BUT PROXMOX Installer is making a POST request
@app.route("/api/answer_file", methods=["POST"])
def answer_file():
    data = request.json
    if not data:
        return make_response(jsonify({"error": "Invalid JSON data"}), 400)
    key = data["network_interfaces"][0].get("mac", "unknown")
    if key in cached_answer_files:
        print(f"Serving cached answer file for {key}")
        # Write the answer file content to a temporary file
        temp = tempfile.NamedTemporaryFile(delete=False, mode="w+", suffix=".toml")
        temp.write(cached_answer_files[key])  # type: ignore
        print(f"Answer file content:\n{cached_answer_files[key]}")
        temp.flush()
        temp.seek(0)
        response = send_file(
            temp.name,
            as_attachment=True,
            download_name="answer_file.toml",
            mimetype="text/plain",
        )
        return response
    else:
        print(f"No cached answer file for {key}")
        # use the data from the request to find the network interface and disk
        return make_response(
            jsonify({"error": "No answer file found for this client"}), 404
        )


@app.route("/api/device_discovery", methods=["POST"])
def device_discovery():
    # print out the req body
    data = request.json
    if not data:
        return make_response(jsonify({"error": "Invalid JSON data"}), 400)

    key = data["mgmt_mac"]
    disk = data["disk"]

    if key not in cached_answer_files:
        cached_answer_files[key] = gen_ans_file_with(key, disk)
        print(f"Generated new answer file for {key}")
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
