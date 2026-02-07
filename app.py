"""
宠物照片分析 - Web 应用
Flask 后端，提供 API 接口供前端调用
"""

import os
import json
import uuid
import base64
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pet_photo_analyzer import (
    PetPhotoAnalyzer, PetPhoto, ALBUM_RULES, CATEGORY_SYSTEM,
    SUPPORTED_FORMATS, encode_image_to_base64, get_image_mime_type
)

app = Flask(__name__)

# 配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100MB 总上传限制

# 全局分析器实例（单用户场景）
analyzer = None


def get_analyzer():
    """获取或创建分析器实例"""
    global analyzer
    if analyzer is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        analyzer = PetPhotoAnalyzer(api_key=api_key)
    return analyzer


# ============================================================
# 页面路由
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


# ============================================================
# API 路由
# ============================================================

@app.route("/api/upload", methods=["POST"])
def upload_photos():
    """批量上传照片"""
    if "photos" not in request.files:
        return jsonify({"error": "没有找到照片文件"}), 400

    files = request.files.getlist("photos")
    if not files or len(files) == 0:
        return jsonify({"error": "请至少上传 1 张照片"}), 400

    if len(files) > 30:
        return jsonify({"error": "单次最多上传 30 张照片"}), 400

    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    # 清空之前的数据
    a.photos = []
    a.analysis_results = {}
    a.albums = {}
    a.pet_profile = {}

    uploaded = []
    for file in files:
        if not file.filename:
            continue

        ext = Path(file.filename).suffix.lower()
        if ext not in SUPPORTED_FORMATS:
            continue

        # 生成安全文件名
        safe_name = f"{uuid.uuid4().hex[:8]}_{secure_filename(file.filename)}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], safe_name)
        file.save(save_path)

        # 创建照片对象并添加到分析器
        photo = PetPhoto(save_path)
        photo.filename = file.filename  # 保留原文件名用于显示
        a.photos.append(photo)

        uploaded.append({
            "photo_id": photo.photo_id,
            "filename": file.filename,
            "display_name": safe_name,
            "url": f"/uploads/{safe_name}",
            "file_size": photo.file_size,
        })

    return jsonify({
        "success": True,
        "uploaded_count": len(uploaded),
        "photos": uploaded,
    })


@app.route("/api/analyze/<photo_id>", methods=["POST"])
def analyze_photo(photo_id):
    """分析单张照片"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    photo = next((p for p in a.photos if p.photo_id == photo_id), None)
    if not photo:
        return jsonify({"error": "照片不存在"}), 404

    if photo.analyzed:
        return jsonify({"success": True, "result": photo.to_dict()})

    result = a.analyze_single_photo(photo)
    if result is None:
        return jsonify({"error": "分析失败，请重试"}), 500

    return jsonify({"success": True, "result": photo.to_dict()})


@app.route("/api/analyze/all", methods=["POST"])
def analyze_all():
    """逐张分析所有照片（同步，返回全部结果）"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    if not a.photos:
        return jsonify({"error": "请先上传照片"}), 400

    results = []
    for photo in a.photos:
        if not photo.analyzed:
            a.analyze_single_photo(photo)
        results.append(photo.to_dict())

    return jsonify({"success": True, "results": results})


@app.route("/api/albums", methods=["GET"])
def get_albums():
    """获取智能相册分类结果"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    a.categorize_into_albums()

    albums_data = {}
    for key, photos in a.albums.items():
        if photos:
            albums_data[key] = {
                "name": ALBUM_RULES[key]["name"],
                "description": ALBUM_RULES[key]["description"],
                "photo_count": len(photos),
                "photos": [p.to_dict() for p in photos],
            }

    return jsonify({"success": True, "albums": albums_data})


@app.route("/api/profile", methods=["GET"])
def get_profile():
    """获取宠物档案"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    profile = a.get_pet_profile()
    if not profile:
        return jsonify({"error": "请先分析照片"}), 400

    return jsonify({"success": True, "profile": profile})


@app.route("/api/tags", methods=["GET"])
def get_tags():
    """获取标签汇总"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    tags = a.get_all_tags()
    return jsonify({
        "success": True,
        "tags": [{"tag": t, "count": c} for t, c in tags],
    })


@app.route("/api/story/prompts", methods=["GET"])
def get_story_prompts():
    """获取故事引导方向"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    a.categorize_into_albums()
    prompts = a.generate_story_prompts()
    return jsonify({"success": True, "prompts": prompts})


@app.route("/api/story/generate", methods=["POST"])
def generate_story():
    """生成宠物故事"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    data = request.get_json()
    if not data:
        return jsonify({"error": "请提供故事方向"}), 400

    story_direction = data.get("story_direction")
    user_notes = data.get("user_notes", "")

    if not story_direction:
        return jsonify({"error": "请选择一个故事方向"}), 400

    story = a.generate_story_with_ai(story_direction, user_notes)
    if not story:
        return jsonify({"error": "故事生成失败"}), 500

    return jsonify({"success": True, "story": story})


@app.route("/api/export", methods=["GET"])
def export_results():
    """导出所有分析结果"""
    a = get_analyzer()
    if a is None:
        return jsonify({"error": "未配置 OPENAI_API_KEY"}), 500

    a.categorize_into_albums()
    a.get_pet_profile()

    results = {
        "export_time": datetime.utcnow().isoformat(),
        "total_photos": len(a.photos),
        "analyzed_photos": sum(1 for p in a.photos if p.analyzed),
        "pet_profile": a.pet_profile,
        "albums": {
            key: {
                "name": ALBUM_RULES[key]["name"],
                "description": ALBUM_RULES[key]["description"],
                "photo_count": len(photos),
                "photos": [p.filename for p in photos],
            }
            for key, photos in a.albums.items()
            if photos
        },
        "all_tags": a.get_all_tags(),
        "photos": [p.to_dict() for p in a.photos],
    }

    return jsonify(results)


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n{'='*50}")
    print(f"  Pet Photo Analyzer Web")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
