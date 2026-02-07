"""
宠物照片分析模块 - Pet Photo Analyzer

功能：
1. 批量上传照片（支持 20-30 张 iPhone 相册照片）
2. 使用 GPT-4 Vision 分析照片内容，提取宠物相关信息
3. 自动为照片打标签并归类（类似 iPhone 相册的智能分类）
4. 引导用户基于照片撰写宠物故事
"""

import os
import sys
import json
import base64
import glob
import hashlib
from datetime import datetime
from pathlib import Path
from openai import OpenAI

# ============================================================
# 配置
# ============================================================

# 支持的图片格式
SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif", ".bmp", ".tiff"}

# 单次上传限制
MIN_PHOTOS = 1
MAX_PHOTOS = 30

# 照片分类体系（类似 iPhone 相册分类）
CATEGORY_SYSTEM = {
    "pet_type": {
        "name": "宠物类型",
        "options": ["狗", "猫", "兔子", "仓鼠", "鸟", "鱼", "爬行动物", "其他"]
    },
    "scene": {
        "name": "场景",
        "options": ["室内", "户外-公园", "户外-街道", "户外-海滩", "户外-山野",
                    "宠物店", "医院/诊所", "车内", "其他"]
    },
    "activity": {
        "name": "活动",
        "options": ["玩耍", "睡觉", "吃东西", "散步", "训练", "洗澡",
                    "与人互动", "与其他动物互动", "发呆", "搞破坏", "其他"]
    },
    "mood": {
        "name": "情绪",
        "options": ["开心", "兴奋", "平静", "好奇", "困倦", "害怕", "生气", "撒娇", "其他"]
    },
    "composition": {
        "name": "构图类型",
        "options": ["特写", "半身", "全身", "远景", "合影", "自拍", "抓拍", "其他"]
    },
    "time_of_day": {
        "name": "时间段",
        "options": ["清晨", "上午", "中午", "下午", "傍晚", "夜晚", "无法判断"]
    },
    "season": {
        "name": "季节",
        "options": ["春", "夏", "秋", "冬", "无法判断"]
    }
}

# 相册分组规则（类似 iPhone 的智能相册）
ALBUM_RULES = {
    "daily_life": {"name": "日常生活", "description": "宠物的日常起居"},
    "outdoor_adventure": {"name": "户外探险", "description": "户外散步和探索"},
    "funny_moments": {"name": "搞笑瞬间", "description": "有趣的表情和动作"},
    "sleeping_beauty": {"name": "睡颜合集", "description": "各种可爱的睡姿"},
    "eating_time": {"name": "美食时刻", "description": "吃东西的样子"},
    "with_friends": {"name": "社交时光", "description": "与人或其他动物的互动"},
    "portrait": {"name": "写真集", "description": "精美的宠物特写和肖像"},
    "growth": {"name": "成长记录", "description": "记录宠物的成长变化"},
}


# ============================================================
# 工具函数
# ============================================================

def log(message, error=False):
    """日志输出"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    log_message = f"[{timestamp}] {message}"
    if error:
        print(log_message, file=sys.stderr)
    else:
        print(log_message)
    sys.stdout.flush()
    sys.stderr.flush()


def encode_image_to_base64(image_path):
    """将图片文件编码为 base64 字符串"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path):
    """根据扩展名返回 MIME 类型"""
    ext = Path(image_path).suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".heic": "image/heic",
    }
    return mime_map.get(ext, "image/jpeg")


def generate_photo_id(image_path):
    """根据文件内容生成唯一 ID"""
    with open(image_path, "rb") as f:
        content_hash = hashlib.md5(f.read()).hexdigest()[:8]
    filename = Path(image_path).stem
    return f"{filename}_{content_hash}"


# ============================================================
# 核心类：照片对象
# ============================================================

class PetPhoto:
    """单张宠物照片的数据结构"""

    def __init__(self, file_path):
        self.file_path = str(Path(file_path).resolve())
        self.photo_id = generate_photo_id(file_path)
        self.filename = Path(file_path).name
        self.file_size = os.path.getsize(file_path)
        self.upload_time = datetime.utcnow().isoformat()

        # AI 分析结果
        self.description = ""          # 照片描述
        self.tags = []                  # 标签列表
        self.categories = {}            # 分类结果 {category_key: value}
        self.pet_info = {}              # 宠物信息 (品种、颜色、大小等)
        self.albums = []                # 所属相册
        self.emotion_score = 0          # 情感分数 (1-10)
        self.story_keywords = []        # 故事关键词
        self.analyzed = False

    def to_dict(self):
        return {
            "photo_id": self.photo_id,
            "filename": self.filename,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "upload_time": self.upload_time,
            "description": self.description,
            "tags": self.tags,
            "categories": self.categories,
            "pet_info": self.pet_info,
            "albums": self.albums,
            "emotion_score": self.emotion_score,
            "story_keywords": self.story_keywords,
            "analyzed": self.analyzed,
        }


# ============================================================
# 核心类：照片分析器
# ============================================================

class PetPhotoAnalyzer:
    """宠物照片分析器 - 使用 GPT-4 Vision 进行照片分析和标签提取"""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("需要提供 OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.photos = []                # 所有照片对象
        self.analysis_results = {}      # photo_id -> 分析结果
        self.albums = {}                # album_key -> [photo_ids]
        self.pet_profile = {}           # 汇总的宠物档案

    # --------------------------------------------------------
    # 1. 照片上传
    # --------------------------------------------------------

    def upload_photos(self, photo_paths):
        """
        批量上传照片

        Args:
            photo_paths: 照片文件路径列表，或包含照片的目录路径

        Returns:
            上传成功的照片数量
        """
        # 如果传入的是目录，自动扫描其中的图片
        if isinstance(photo_paths, str) and os.path.isdir(photo_paths):
            photo_paths = self._scan_directory(photo_paths)

        if isinstance(photo_paths, str):
            photo_paths = [photo_paths]

        # 验证数量
        if len(photo_paths) < MIN_PHOTOS:
            log(f"⚠️ 至少需要上传 {MIN_PHOTOS} 张照片", error=True)
            return 0
        if len(photo_paths) > MAX_PHOTOS:
            log(f"⚠️ 单次最多上传 {MAX_PHOTOS} 张照片，当前 {len(photo_paths)} 张", error=True)
            log(f"   将只处理前 {MAX_PHOTOS} 张")
            photo_paths = photo_paths[:MAX_PHOTOS]

        uploaded = 0
        for path in photo_paths:
            path = str(path)
            # 检查文件是否存在
            if not os.path.isfile(path):
                log(f"⚠️ 文件不存在，跳过: {path}")
                continue

            # 检查格式
            ext = Path(path).suffix.lower()
            if ext not in SUPPORTED_FORMATS:
                log(f"⚠️ 不支持的格式 {ext}，跳过: {path}")
                continue

            # 创建照片对象
            photo = PetPhoto(path)
            self.photos.append(photo)
            uploaded += 1
            log(f"📸 已上传: {photo.filename} (ID: {photo.photo_id})")

        log(f"✅ 共上传 {uploaded} 张照片")
        return uploaded

    def _scan_directory(self, directory):
        """扫描目录中的所有图片文件"""
        image_files = []
        for ext in SUPPORTED_FORMATS:
            image_files.extend(glob.glob(os.path.join(directory, f"*{ext}")))
            image_files.extend(glob.glob(os.path.join(directory, f"*{ext.upper()}")))
        image_files.sort()
        log(f"📂 在目录 {directory} 中找到 {len(image_files)} 张图片")
        return image_files

    # --------------------------------------------------------
    # 2. 照片分析（GPT-4 Vision）
    # --------------------------------------------------------

    def analyze_single_photo(self, photo):
        """
        使用 GPT-4 Vision 分析单张照片

        返回结构化的分析结果
        """
        log(f"🔍 正在分析: {photo.filename}...")

        base64_image = encode_image_to_base64(photo.file_path)
        mime_type = get_image_mime_type(photo.file_path)

        analysis_prompt = f"""你是一个专业的宠物照片分析师。请仔细分析这张照片，并以 JSON 格式返回以下信息：

{{
    "description": "用2-3句话描述这张照片的内容，重点描述宠物的状态",
    "pet_info": {{
        "type": "宠物类型（狗/猫/兔子/仓鼠/鸟/鱼/爬行动物/其他/无宠物）",
        "breed": "品种（如果能识别的话，否则填'未知'）",
        "color": "主要毛色/体色",
        "size": "体型（小型/中型/大型）",
        "estimated_age": "大致年龄段（幼年/青年/成年/老年/无法判断）",
        "distinctive_features": "显著特征（如特殊花纹、配饰等）"
    }},
    "categories": {{
        "pet_type": "从 {CATEGORY_SYSTEM['pet_type']['options']} 中选择",
        "scene": "从 {CATEGORY_SYSTEM['scene']['options']} 中选择",
        "activity": "从 {CATEGORY_SYSTEM['activity']['options']} 中选择",
        "mood": "从 {CATEGORY_SYSTEM['mood']['options']} 中选择",
        "composition": "从 {CATEGORY_SYSTEM['composition']['options']} 中选择",
        "time_of_day": "从 {CATEGORY_SYSTEM['time_of_day']['options']} 中选择",
        "season": "从 {CATEGORY_SYSTEM['season']['options']} 中选择"
    }},
    "tags": ["标签1", "标签2", "...最多10个相关标签，包括宠物特征、场景、情绪、活动等"],
    "emotion_score": "照片传达的情感温暖度（1-10，10最温暖）",
    "story_keywords": ["关键词1", "关键词2", "...3-5个可用于生成故事的关键词"],
    "suggested_albums": ["从以下选项中选择适合的相册: {list(ALBUM_RULES.keys())}"]
}}

请确保返回有效的 JSON 格式，不要添加其他文字。"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}",
                                    "detail": "high"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
                temperature=0.3,
            )

            result_text = response.choices[0].message.content.strip()

            # 提取 JSON（处理可能的 markdown 代码块包裹）
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1]
                result_text = result_text.rsplit("```", 1)[0]
            result_text = result_text.strip()

            result = json.loads(result_text)

            # 将结果写入照片对象
            photo.description = result.get("description", "")
            photo.tags = result.get("tags", [])
            photo.categories = result.get("categories", {})
            photo.pet_info = result.get("pet_info", {})
            photo.emotion_score = result.get("emotion_score", 5)
            photo.story_keywords = result.get("story_keywords", [])
            photo.albums = result.get("suggested_albums", [])
            photo.analyzed = True

            self.analysis_results[photo.photo_id] = result
            log(f"✅ 分析完成: {photo.filename} | 标签: {', '.join(photo.tags[:5])}")
            return result

        except json.JSONDecodeError as e:
            log(f"❌ JSON 解析失败 ({photo.filename}): {e}", error=True)
            log(f"   原始返回: {result_text[:200]}", error=True)
            return None
        except Exception as e:
            log(f"❌ 分析失败 ({photo.filename}): {e}", error=True)
            return None

    def analyze_all_photos(self):
        """批量分析所有未分析的照片"""
        unanalyzed = [p for p in self.photos if not p.analyzed]
        if not unanalyzed:
            log("ℹ️ 所有照片已分析完毕")
            return

        log(f"🚀 开始分析 {len(unanalyzed)} 张照片...")
        success = 0
        for i, photo in enumerate(unanalyzed, 1):
            log(f"--- 进度: {i}/{len(unanalyzed)} ---")
            result = self.analyze_single_photo(photo)
            if result:
                success += 1

        log(f"🎉 分析完成！成功 {success}/{len(unanalyzed)} 张")

    # --------------------------------------------------------
    # 3. 照片归类（类似 iPhone 智能相册）
    # --------------------------------------------------------

    def categorize_into_albums(self):
        """
        将照片自动归类到智能相册中

        Returns:
            albums: dict, album_key -> [PetPhoto]
        """
        self.albums = {key: [] for key in ALBUM_RULES}

        for photo in self.photos:
            if not photo.analyzed:
                continue

            categories = photo.categories
            activity = categories.get("activity", "")
            scene = categories.get("scene", "")
            mood = categories.get("mood", "")
            composition = categories.get("composition", "")

            # 日常生活
            if activity in ["发呆", "玩耍"] and scene == "室内":
                self.albums["daily_life"].append(photo)

            # 户外探险
            if scene.startswith("户外"):
                self.albums["outdoor_adventure"].append(photo)

            # 搞笑瞬间
            if mood in ["兴奋", "好奇"] or activity == "搞破坏":
                self.albums["funny_moments"].append(photo)

            # 睡颜合集
            if activity == "睡觉" or mood == "困倦":
                self.albums["sleeping_beauty"].append(photo)

            # 美食时刻
            if activity == "吃东西":
                self.albums["eating_time"].append(photo)

            # 社交时光
            if activity in ["与人互动", "与其他动物互动"] or composition == "合影":
                self.albums["with_friends"].append(photo)

            # 写真集
            if composition in ["特写", "半身"] and photo.emotion_score >= 7:
                self.albums["portrait"].append(photo)

            # 基于 AI 建议的相册
            for album_key in photo.albums:
                if album_key in self.albums and photo not in self.albums[album_key]:
                    self.albums[album_key].append(photo)

        # 输出分类结果
        log("\n📁 智能相册分类结果:")
        log("=" * 50)
        for key, photos in self.albums.items():
            if photos:
                rule = ALBUM_RULES[key]
                log(f"  📂 {rule['name']} ({rule['description']}): {len(photos)} 张")
                for p in photos:
                    log(f"      - {p.filename}: {p.description[:40]}...")

        return self.albums

    # --------------------------------------------------------
    # 4. 标签汇总
    # --------------------------------------------------------

    def get_all_tags(self):
        """获取所有照片的标签汇总"""
        tag_count = {}
        for photo in self.photos:
            if not photo.analyzed:
                continue
            for tag in photo.tags:
                tag_count[tag] = tag_count.get(tag, 0) + 1

        # 按频率排序
        sorted_tags = sorted(tag_count.items(), key=lambda x: x[1], reverse=True)
        return sorted_tags

    def get_pet_profile(self):
        """
        根据所有照片汇总宠物档案

        通过统计所有照片的分析结果，生成一个综合的宠物档案
        """
        if not any(p.analyzed for p in self.photos):
            return {}

        analyzed_photos = [p for p in self.photos if p.analyzed]

        # 统计宠物类型
        pet_types = {}
        breeds = {}
        colors = {}
        for p in analyzed_photos:
            pet_type = p.pet_info.get("type", "未知")
            breed = p.pet_info.get("breed", "未知")
            color = p.pet_info.get("color", "未知")
            pet_types[pet_type] = pet_types.get(pet_type, 0) + 1
            breeds[breed] = breeds.get(breed, 0) + 1
            colors[color] = colors.get(color, 0) + 1

        # 取最常见的
        main_type = max(pet_types, key=pet_types.get) if pet_types else "未知"
        main_breed = max(breeds, key=breeds.get) if breeds else "未知"
        main_color = max(colors, key=colors.get) if colors else "未知"

        # 情感平均分
        avg_emotion = sum(p.emotion_score for p in analyzed_photos) / len(analyzed_photos)

        # 收集所有故事关键词
        all_keywords = []
        for p in analyzed_photos:
            all_keywords.extend(p.story_keywords)

        self.pet_profile = {
            "pet_type": main_type,
            "breed": main_breed,
            "main_color": main_color,
            "photo_count": len(analyzed_photos),
            "avg_emotion_score": round(avg_emotion, 1),
            "top_tags": self.get_all_tags()[:15],
            "story_keywords": list(set(all_keywords)),
            "distinctive_features": list({
                p.pet_info.get("distinctive_features", "")
                for p in analyzed_photos
                if p.pet_info.get("distinctive_features")
            }),
        }

        log("\n🐾 宠物档案:")
        log("=" * 50)
        log(f"  类型: {main_type}")
        log(f"  品种: {main_breed}")
        log(f"  毛色: {main_color}")
        log(f"  照片数: {len(analyzed_photos)}")
        log(f"  情感均分: {avg_emotion:.1f}/10")
        log(f"  热门标签: {', '.join(t[0] for t in self.pet_profile['top_tags'][:10])}")

        return self.pet_profile

    # --------------------------------------------------------
    # 5. 宠物故事引导
    # --------------------------------------------------------

    def generate_story_prompts(self):
        """
        基于照片分析结果，生成宠物故事引导提示

        返回多个故事方向供用户选择
        """
        if not self.pet_profile:
            self.get_pet_profile()

        profile = self.pet_profile
        albums = self.albums

        story_directions = []

        # 方向1: 日常温馨故事
        if albums.get("daily_life"):
            daily_photos = albums["daily_life"]
            keywords = []
            for p in daily_photos:
                keywords.extend(p.story_keywords)
            story_directions.append({
                "title": "日常小确幸",
                "description": f"记录你和{profile['breed']}的日常生活点滴",
                "prompt": f"基于这些日常照片，写一篇关于你和你的{profile['pet_type']}（{profile['breed']}）"
                          f"在家中的温馨日常故事。可以围绕这些关键词展开：{', '.join(set(keywords)[:5])}",
                "related_photos": [p.filename for p in daily_photos],
            })

        # 方向2: 户外冒险故事
        if albums.get("outdoor_adventure"):
            outdoor_photos = albums["outdoor_adventure"]
            scenes = list({p.categories.get("scene", "") for p in outdoor_photos})
            story_directions.append({
                "title": "户外探险记",
                "description": f"讲述你们一起外出探索的故事",
                "prompt": f"写一篇关于你带{profile['breed']}去户外冒险的故事。"
                          f"你们去过的地方包括：{', '.join(scenes)}。"
                          f"描述一次最难忘的户外经历。",
                "related_photos": [p.filename for p in outdoor_photos],
            })

        # 方向3: 成长故事
        if len(self.photos) >= 5:
            all_keywords = profile.get("story_keywords", [])
            story_directions.append({
                "title": "成长的故事",
                "description": "从第一张照片到现在，记录你们一起成长的历程",
                "prompt": f"看着这 {len(self.photos)} 张照片，回忆你和你的{profile['pet_type']}一起走过的日子。"
                          f"从你们相遇的那一天开始说起，讲述你们之间的故事。"
                          f"关键词参考：{', '.join(all_keywords[:8])}",
                "related_photos": [p.filename for p in self.photos[:5]],
            })

        # 方向4: 搞笑瞬间
        if albums.get("funny_moments"):
            funny_photos = albums["funny_moments"]
            story_directions.append({
                "title": "爆笑日记",
                "description": "那些让你捧腹大笑的瞬间",
                "prompt": f"你的{profile['breed']}总是能做出让人意想不到的事情。"
                          f"选择照片中最搞笑的一个瞬间，详细描述当时发生了什么。",
                "related_photos": [p.filename for p in funny_photos],
            })

        # 方向5: 情感连接
        if albums.get("with_friends"):
            social_photos = albums["with_friends"]
            story_directions.append({
                "title": "我们的羁绊",
                "description": "关于你和宠物之间特殊情感连接的故事",
                "prompt": f"看着你们的合影，写一封给你的{profile['pet_type']}的信。"
                          f"告诉它你有多爱它，分享你们之间最特别的回忆。",
                "related_photos": [p.filename for p in social_photos],
            })

        return story_directions

    def generate_story_with_ai(self, story_direction, user_notes=""):
        """
        使用 AI 根据选定的故事方向和照片生成故事草稿

        Args:
            story_direction: 从 generate_story_prompts 返回的某个故事方向
            user_notes: 用户的补充说明

        Returns:
            生成的故事文本
        """
        profile = self.pet_profile

        system_prompt = """你是一位善于捕捉宠物与人之间温暖瞬间的故事作家。
你会基于照片分析结果和用户的描述，帮助用户写出真挚、温暖、有画面感的宠物故事。
故事要自然亲切，像是在和朋友分享，不要太正式。
长度控制在 300-500 字之间。"""

        user_prompt = f"""请帮我写一篇宠物故事。

故事方向: {story_direction['title']}
提示: {story_direction['prompt']}

我的宠物信息:
- 类型: {profile.get('pet_type', '未知')}
- 品种: {profile.get('breed', '未知')}
- 毛色: {profile.get('main_color', '未知')}
- 特征: {', '.join(profile.get('distinctive_features', []))}

相关照片描述:
"""
        # 添加相关照片的描述
        for filename in story_direction.get("related_photos", [])[:5]:
            for photo in self.photos:
                if photo.filename == filename and photo.analyzed:
                    user_prompt += f"- {filename}: {photo.description}\n"
                    break

        if user_notes:
            user_prompt += f"\n我的补充说明: {user_notes}\n"

        user_prompt += "\n请为我写一篇温暖的宠物故事："

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1500,
                temperature=0.8,
            )
            story = response.choices[0].message.content.strip()
            log(f"✅ 故事生成完成: {story_direction['title']}")
            return story
        except Exception as e:
            log(f"❌ 故事生成失败: {e}", error=True)
            return None

    # --------------------------------------------------------
    # 6. 导出结果
    # --------------------------------------------------------

    def export_results(self, output_path="photo_analysis_results.json"):
        """将所有分析结果导出为 JSON 文件"""
        results = {
            "export_time": datetime.utcnow().isoformat(),
            "total_photos": len(self.photos),
            "analyzed_photos": sum(1 for p in self.photos if p.analyzed),
            "pet_profile": self.pet_profile,
            "albums": {
                key: {
                    "name": ALBUM_RULES[key]["name"],
                    "description": ALBUM_RULES[key]["description"],
                    "photo_count": len(photos),
                    "photos": [p.filename for p in photos],
                }
                for key, photos in self.albums.items()
                if photos
            },
            "all_tags": self.get_all_tags(),
            "photos": [p.to_dict() for p in self.photos],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        log(f"💾 结果已导出: {output_path}")
        return output_path


# ============================================================
# 主交互流程
# ============================================================

def run_interactive():
    """交互式运行主流程"""
    print("\n" + "=" * 60)
    print("🐾 宠物照片分析助手 - Pet Photo Analyzer")
    print("=" * 60)
    print("欢迎使用！请按照提示操作。\n")

    # 初始化分析器
    try:
        analyzer = PetPhotoAnalyzer()
    except ValueError as e:
        print(f"❌ 初始化失败: {e}")
        print("请设置环境变量 OPENAI_API_KEY")
        return

    # Step 1: 上传照片
    print("📸 第一步：上传照片")
    print("-" * 40)
    print(f"请提供照片目录路径或逐个输入照片路径（支持 {MIN_PHOTOS}-{MAX_PHOTOS} 张）")
    print("支持格式:", ", ".join(SUPPORTED_FORMATS))

    photo_input = input("\n请输入照片目录路径（或输入 'manual' 逐个添加）: ").strip()

    if photo_input.lower() == "manual":
        paths = []
        print("请逐个输入照片路径（输入 'done' 结束）:")
        while len(paths) < MAX_PHOTOS:
            path = input(f"  照片 {len(paths) + 1}: ").strip()
            if path.lower() == "done":
                break
            if os.path.isfile(path):
                paths.append(path)
            else:
                print(f"  ⚠️ 文件不存在: {path}")
        uploaded = analyzer.upload_photos(paths)
    else:
        uploaded = analyzer.upload_photos(photo_input)

    if uploaded == 0:
        print("❌ 没有成功上传任何照片，退出。")
        return

    # Step 2: 分析照片
    print(f"\n🔍 第二步：分析照片（共 {uploaded} 张）")
    print("-" * 40)
    confirm = input("开始分析？(y/n): ").strip().lower()
    if confirm != "y":
        print("已取消。")
        return

    analyzer.analyze_all_photos()

    # Step 3: 查看分类结果
    print(f"\n📁 第三步：查看智能相册分类")
    print("-" * 40)
    albums = analyzer.categorize_into_albums()

    # Step 4: 查看宠物档案
    print(f"\n🐾 第四步：宠物档案")
    print("-" * 40)
    profile = analyzer.get_pet_profile()

    # Step 5: 查看标签
    print(f"\n🏷️ 第五步：标签汇总")
    print("-" * 40)
    tags = analyzer.get_all_tags()
    print("热门标签:")
    for tag, count in tags[:20]:
        print(f"  #{tag} (x{count})")

    # Step 6: 故事引导
    print(f"\n📖 第六步：宠物故事")
    print("-" * 40)
    story_prompts = analyzer.generate_story_prompts()

    if story_prompts:
        print("为你推荐以下故事方向:\n")
        for i, sp in enumerate(story_prompts, 1):
            print(f"  {i}. {sp['title']} - {sp['description']}")
            print(f"     相关照片: {', '.join(sp['related_photos'][:3])}")
            print()

        choice = input("选择一个故事方向（输入编号，或 'skip' 跳过）: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(story_prompts):
            selected = story_prompts[int(choice) - 1]
            notes = input("有什么想补充的吗？（直接回车跳过）: ").strip()
            print("\n✍️ 正在为你生成故事...\n")
            story = analyzer.generate_story_with_ai(selected, notes)
            if story:
                print("=" * 60)
                print(story)
                print("=" * 60)

    # Step 7: 导出
    print(f"\n💾 第七步：导出结果")
    print("-" * 40)
    export_path = input("导出文件路径（直接回车使用默认路径）: ").strip()
    if not export_path:
        export_path = "photo_analysis_results.json"
    analyzer.export_results(export_path)

    print("\n🎉 全部完成！感谢使用宠物照片分析助手！")


# ============================================================
# 程序入口
# ============================================================

if __name__ == "__main__":
    run_interactive()
