import logging
import os
from typing import Any, Dict

import requests
from flask import Flask, jsonify, render_template, request

from cache_manager_new import cache_manager
from prizm_client import PrizmClient, PrizmLookupError, normalize_postal_code

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
prizm_client = PrizmClient()


@app.before_request
def require_api_key():
    expected_key = os.environ.get("PRIZM_API_KEY")
    if not expected_key or not request.path.startswith("/api/") or request.method == "OPTIONS":
        return None

    provided_key = request.headers.get("X-API-Key")
    auth_header = request.headers.get("Authorization", "")
    bearer_token = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else None

    if provided_key == expected_key or bearer_token == expected_key:
        return None

    return jsonify({"error": "Unauthorized"}), 401


def api_response_from_cache(cached_data: Dict[str, Any]) -> Dict[str, Any]:
    response = cached_data.copy()
    segment_number = response.get("segment_number")
    response["prizm_code"] = segment_number or "Unknown"

    if response.get("status") == "invalid":
        response["prizm_code"] = "Unknown"

    cache_info = response.pop("_cache_info", None)
    if cache_info:
        response["cache_info"] = cache_info

    return response


def get_prizm_code(postal_code: str) -> Dict[str, Any]:
    formatted_postal_code = normalize_postal_code(postal_code)
    cache_key = formatted_postal_code or postal_code

    cached_data = cache_manager.get_cached_data(cache_key)
    if cached_data:
        logger.info("Returning cached PRIZM result for %s", cache_key)
        return api_response_from_cache(cached_data)

    try:
        result = prizm_client.lookup(postal_code)
        should_cache = True
    except (PrizmLookupError, requests.RequestException) as exc:
        logger.exception("PRIZM lookup failed for %s", postal_code)
        should_cache = False
        result = {
            "postal_code": formatted_postal_code or postal_code,
            "prizm_code": "Unknown",
            "segment_number": None,
            "segment_name": "",
            "segment_description": "",
            "average_household_income": "",
            "education": "",
            "urbanity": "",
            "average_household_net_worth": "",
            "occupation": "",
            "diversity": "",
            "family_life": "",
            "tenure": "",
            "home_type": "",
            "status": "error",
            "message": str(exc),
        }

    if should_cache:
        cache_duration = 7 if result["status"] == "error" else None
        cache_manager.cache_data(cache_key, result, custom_duration_days=cache_duration)
    return result


@app.route("/")
def home():
    try:
        return render_template("index.html")
    except Exception:
        return jsonify(
            {
                "name": "PRIZM Code Lookup API",
                "status": "ok",
                "endpoints": {
                    "single": "GET /api/prizm?postal_code=V8A0A8",
                    "batch": "POST /api/prizm/batch",
                    "health": "GET /health",
                },
            }
        )


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Service is running"})


@app.route("/api/prizm", methods=["GET"])
def get_single_prizm():
    postal_code = request.args.get("postal_code")
    if not postal_code:
        return jsonify({"error": "postal_code is required"}), 400

    return jsonify(get_prizm_code(postal_code))


@app.route("/api/prizm/batch", methods=["POST"])
def get_batch_prizm():
    data = request.get_json(silent=True) or {}
    postal_codes = data.get("postal_codes")

    if not isinstance(postal_codes, list) or not postal_codes:
        return jsonify({"error": "postal_codes must be a non-empty list"}), 400

    max_postal_codes = int(os.environ.get("MAX_BATCH_POSTAL_CODES", "10"))
    if len(postal_codes) > max_postal_codes:
        return jsonify({"error": f"Too many postal codes. Maximum allowed is {max_postal_codes}."}), 400

    results = [get_prizm_code(str(postal_code)) for postal_code in postal_codes]
    return jsonify(
        {
            "results": results,
            "total": len(results),
            "successful": sum(1 for result in results if result["status"] == "success"),
            "failed": sum(1 for result in results if result["status"] != "success"),
        }
    )


@app.route("/api/segments", methods=["GET"])
def get_segments():
    return jsonify({"status": "success", "segments": prizm_client.get_all_segments()})


@app.route("/api/cache/stats", methods=["GET"])
def get_cache_stats():
    return jsonify({"status": "success", "cache_stats": cache_manager.get_cache_stats()})


@app.route("/api/cache/cleanup", methods=["POST"])
def cleanup_cache():
    deleted_count = cache_manager.cleanup_expired_cache()
    return jsonify({"status": "success", "message": f"Cleaned up {deleted_count} expired cache entries"})


@app.route("/api/cache/clear", methods=["POST"])
def clear_cache():
    if cache_manager.clear_cache():
        return jsonify({"status": "success", "message": "All cache entries cleared"})
    return jsonify({"status": "error", "error": "Failed to clear cache"}), 500


@app.route("/api/cache/check/<postal_code>", methods=["GET"])
def check_cache(postal_code):
    is_cached = cache_manager.is_cached(postal_code)
    cached_data = cache_manager.get_cached_data(postal_code) if is_cached else None
    return jsonify(
        {
            "status": "success",
            "postal_code": postal_code,
            "is_cached": is_cached,
            "cached_at": cached_data.get("_cache_info", {}).get("cached_at") if cached_data else None,
        }
    )


@app.route("/api/cache/delete/<postal_code>", methods=["DELETE"])
def delete_cache_entry(postal_code):
    if cache_manager.delete_cached_data(postal_code):
        return jsonify({"status": "success", "message": f"Successfully deleted cache entry for {postal_code}"})
    return jsonify({"status": "error", "error": f"No cache entry found for {postal_code}"}), 404


@app.route("/api/cache/confirm/<postal_code>", methods=["POST"])
def confirm_cache_entry(postal_code):
    if cache_manager.confirm_data(postal_code):
        return jsonify({"status": "success", "message": f"Successfully confirmed data for {postal_code}"})
    return jsonify({"status": "error", "error": f"No valid cache entry found for {postal_code}"}), 404


@app.route("/api/cache/unconfirm/<postal_code>", methods=["POST"])
def unconfirm_cache_entry(postal_code):
    if cache_manager.unconfirm_data(postal_code):
        return jsonify({"status": "success", "message": f"Successfully unconfirmed data for {postal_code}"})
    return jsonify({"status": "error", "error": f"No valid cache entry found for {postal_code}"}), 404


@app.route("/api/cache/unconfirmed", methods=["GET"])
def get_unconfirmed_entries():
    limit = request.args.get("limit", 100, type=int)
    entries = cache_manager.get_unconfirmed_entries(limit)
    return jsonify({"status": "success", "unconfirmed_entries": entries, "count": len(entries)})


@app.route("/api/debug/html/<postal_code>", methods=["GET"])
def get_debug_html(postal_code):
    html_content = cache_manager.get_cached_html(postal_code)
    if html_content:
        return html_content, 200, {"Content-Type": "text/html; charset=utf-8"}
    return jsonify({"status": "error", "error": f"No HTML content found for postal code {postal_code}"}), 404


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = os.environ.get("CORS_ALLOW_ORIGIN", "*")
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return response


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
