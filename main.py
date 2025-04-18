import os
import openai
import praw
import random
import time
import sys
import traceback
from datetime import datetime, timedelta

# === 配置日志 ===
def log(message, error=False):
    """增强的日志记录，带时间戳和流刷新"""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    log_message = f"[{timestamp}] {message}"
    
    if error:
        print(log_message, file=sys.stderr)
    else:
        print(log_message)
    
    # 强制刷新以确保日志立即显示
    sys.stdout.flush()
    sys.stderr.flush()

# 以清晰的状态消息开始
log("👋 脚本启动中...")

# === 检查环境变量 ===
required_env_vars = [
    "OPENAI_API_KEY", 
    "CLIENT_ID", 
    "CLIENT_SECRET", 
    "REFRESH_TOKEN", 
    "USER_AGENT"
]

missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    log(f"❌ 错误: 缺少必要的环境变量: {', '.join(missing_vars)}", error=True)
    log("⛔ 脚本因配置缺失而退出", error=True)
    sys.exit(1)

# 记录环境变量加载成功
for var in required_env_vars:
    value = os.getenv(var)
    masked_value = f"{value[:3]}...{value[-3:]}" if value else "未设置"
    log(f"✅ {var} 已加载: {masked_value}")

# === 配置信息 ===
openai.api_key = os.getenv("OPENAI_API_KEY")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("REFRESH_TOKEN")
USER_AGENT = os.getenv("USER_AGENT")

# === 发帖目标社区配置 ===
TARGET_SUBREDDIT = "C25K"  # 只在C25K社区发帖
SUBREDDITS_CONFIG = {
    TARGET_SUBREDDIT: {"flair_id": None, "flair_text": None}  # 如果C25K需要flair，则更新此处
}

# === 评论目标社区与关键词 ===
COMMENT_SUBREDDITS = [
    # 高优先级（与马拉松相关）
    "running", "marathon", "marathontraining", "firstmarathon", 
    "loseit", "fitness", "progresspics",
    
    # 中等优先级
    "bodyweightfitness", "xxfitness", "HealthyFood", "intermittentfasting",
    "getdisciplined", "selfimprovement", "productivity", "decidingtobebetter",
    "QuantifiedSelf", "AppleWatch",
    
    # 低优先级但高karma潜力
    "AskReddit", "NoStupidQuestions", "LifeProTips", "simpleliving", 
    "gadgets", "technology"
]

# 更宽泛的关键词，增加匹配几率以提高karma
KEYWORDS = ["run", "running", "train", "training", "struggle", "struggling", "motivation", "motivate", 
           "plan", "planning", "start", "begin", "beginning", "days", "week", "month", "journey", 
           "goal", "goals", "fitness", "exercise", "routine", "habit", "progress", "challenge", 
           "advice", "help", "tips", "question", "experience", "story", "update", "achievement",
           "app", "track", "tracking", "data", "marathon", "health", "healthy", "weight", "loss",
           "discipline", "consistency", "distance", "pace", "program", "schedule", "improvement"]

# App相关关键词
TRACKING_KEYWORDS = ["track", "tracking", "log", "record", "monitor", "data", "stats", "progress"]
APP_REQUEST_KEYWORDS = ["app", "recommend", "recommendation", "tool", "software", "program", "which app", "best app"]
PLAN_KEYWORDS = ["plan", "schedule", "program", "routine", "training", "preparation", "coach"]

# === 时间和评论限制参数 ===
INTERVAL_BETWEEN_COMMENTS = 5  # 每两条评论间隔（分钟）
MIN_DAILY_COMMENTS = 90  # 每天至少评论数
MAX_DAILY_COMMENTS = 110  # 每天最多评论数
MAX_COMMENT_LENGTH = 400  # 减少字数，20-80词大约是80-400字符

# === 全局变量追踪 ===
# 帖子追踪
last_post_date = datetime(2025, 4, 17).date()  # 指定最后一次发帖的日期
log_file = "patrick_post_log.txt"

# 评论追踪
commented_ids = set()
comment_count = 0
last_reset_date = datetime.now().date()
last_comment_time = None
comment_log_file = "comment_log.txt"

# App提及追踪
app_mentions_count = 0
app_mentions_today = 0
last_app_mention_reset = datetime.now().date()

# === 帖子历史记录 ===
# === 帖子历史记录 ===
post_history = [
    {
        "day": 1,
        "title": "Day 1: Every marathon journey starts with a single step!",
        "body": """This is Patrick here, your humble running coach and newbie marathon trainee. So, today is DAY 1 of my grand 100-day marathon training challenge, and guess what? I've successfully run a grand total of... 0 km. Yep, you read that right! I know some of you are thinking, "Oh, that's not a great start, Patrick." But hey, every journey, even a 42.195 km one, starts with a single step, right?

I've got to admit, the toughest part was not the run itself, but getting out of bed in the pre-dawn darkness. Trust me, the struggle is real! But the post-run exhilaration, wow, it's worth every sleepy-eyed curse word I muttered this morning.

I'd love to hear how you guys deal with the early morning hustle. Do you have any tricks up your sleeve to make waking up less of a battle? Any funny stories to share?

Here's to the next 99 days and beyond! Let's hit the track, metaphorically or otherwise, and support each other on this journey.

Keep running, keep smiling!

Patrick"""
    },
    {
        "day": 2,
        "title": "Day 2 of 100: Dawn Runs, Sore Muscles, and the Joy of Progress",
        "body": """Good morning, fellow runners! Patrick here, back at it for Day 2 of my 100-day marathon training challenge. This morning, I successfully set my alarm early again, dragged my slightly achy self out of bed, and hit the quiet, crisp streets while most were still dreaming.

I've clocked another few kilometers today, and let me tell you, my muscles are feeling it! I'm sure some of you can relate. But remember, no pain, no gain, right? It's all part of our journey from the couch to the 5k track and beyond!

I'm curious, how do you guys cope with muscle soreness? Do you have any favorite stretches or recovery routines? Also, to you early birds out there, how was your dawn run today? I find the quiet solitude of the early morning to be the perfect time to reflect and set my intentions for the day.

Here's to another day of progress, no matter how small. Remember, every kilometer counts in this journey, and the most challenging strides often lead to the greatest rewards!

Keep running, keep smiling, and keep sharing your stories. I'm with you every step of the way!

Yours in running,
Patrick"""
    }
]


# 更新历史记录函数
def update_post_history(day, title, body):
    """将新帖子添加到历史记录中"""
    post_history.append({
        "day": day,
        "title": title,
        "body": body
    })
    # 保持历史记录不超过7天（最近一周）
    if len(post_history) > 7:
        post_history.pop(0)
    
    # 同时保存到永久存储
    try:
        with open("post_history.txt", "a", encoding="utf-8") as f:
            f.write(f"\n\n===== DAY {day} =====\n")
            f.write(f"Title: {title}\n\n")
            f.write(body)
            f.write("\n\n----------\n")
    except Exception as e:
        log(f"⚠️ 警告: 无法保存帖子历史到文件: {str(e)}", error=True)

# === 初始化 Reddit ===
try:
    log("🔄 初始化Reddit API连接...")
    reddit = praw.Reddit(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        refresh_token=REFRESH_TOKEN,
        user_agent=USER_AGENT,
    )
    # 通过检查用户名验证凭据
    username = reddit.user.me().name
    log(f"✅ 成功认证为用户: {username}")
except Exception as e:
    log(f"❌ Reddit API初始化失败: {str(e)}", error=True)
    log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
    log("⛔ 脚本因Reddit API失败而退出", error=True)
    sys.exit(1)

# === Patrick 的当前状态（用作上下文保持） ===
patrick_state = {
    "day": 3,  # 今天是第3天, 因为已经发过了第1天和第2天
    "total_km": 10,  # 假设已经累计跑了10公里
    "mood": "tired but focused",  # 第三天的心情
    "struggles": ["muscle soreness", "early mornings"],  # 第三天的挑战
}

# === 情绪变化日历（每7天切换一次） ===
mood_cycle = [
    ("optimistic", ["early mornings"]),
    ("determined", ["muscle soreness"]),
    ("tired but focused", ["motivation dips"]),
    ("energized", ["balancing work and training"]),
    ("reflective", ["self-doubt", "weather"]),
    ("confident", ["nothing specific"]),
    ("grateful", ["the long journey"]),
]

# === 获取当前UK时间 ===
def get_uk_time():
    """返回英国当前时间（基于UTC+1，适用于British Summer Time）"""
    # 英国夏令时UTC+1，冬令时UTC+0
    # 这里假设我们在夏令时，根据需要可调整
    utc_time = datetime.utcnow()
    uk_time = utc_time + timedelta(hours=1)  # BST (UTC+1)
    return uk_time

# === 检查今天是否已发帖 ===
def should_post_today():
    """检查今天（按英国时区）是否需要发帖"""
    uk_now = get_uk_time()
    uk_today = uk_now.date()
    
    if last_post_date is None:
        log(f"🗓️ 尚未发过帖子，今天需要发帖")
        return True
        
    # 如果最后发帖日期不是今天，则需要发帖
    if last_post_date != uk_today:
        log(f"🗓️ 最后发帖日期是 {last_post_date}，今天是 {uk_today}，需要发帖")
        return True
    
    log(f"🗓️ 今天已经发过帖子了 ({uk_today})")
    return False

# === 检查是否在发帖时间窗口内 ===
def is_posting_time():
    """检查当前时间是否在发帖时间窗口内（英国时间11点到20点）"""
    uk_now = get_uk_time()
    hour = uk_now.hour
    
    if 11 <= hour < 20:
        return True
    else:
        log(f"⏰ 当前UK时间 {uk_now.strftime('%H:%M')} 超出发帖时间窗口 (11:00-20:00)")
        return False

# === 根据发帖时间确定训练时段 ===
def get_training_time_context():
    """根据当前UK时间确定合适的训练时段描述"""
    uk_now = get_uk_time()
    hour = uk_now.hour
    
    if 11 <= hour < 13:
        # 上午11点到下午1点 - 假设是晨跑
        return {
            "when": "early morning",
            "time_desc": "dawn", 
            "details": "I set my alarm early and dragged myself out of bed while most people were still sleeping. The streets were quiet, and the morning air was crisp."
        }
    elif 13 <= hour < 16:
        # 下午1点到4点 - 假设是早上跑步
        return {
            "when": "this morning",
            "time_desc": "morning", 
            "details": "I decided to start my day with a run. The morning was bright, and there were already people commuting to work when I hit the pavement."
        }
    elif 16 <= hour < 18:
        # 下午4点到6点 - 假设是午餐时间跑步
        return {
            "when": "during my lunch break",
            "time_desc": "midday", 
            "details": "I squeezed in a quick run during my lunch break today. It was a perfect way to break up the day and refresh my mind."
        }
    else:  # 18-20点
        # 晚上6点到8点 - 假设是下班后跑步
        return {
            "when": "after work",
            "time_desc": "evening", 
            "details": "I went for a run after finishing work today. The sunset was beautiful, and there were lots of other runners out enjoying the evening."
        }

# === 分析是否可以自然提及app ===
def can_naturally_mention_app(post_title, post_content, subreddit):
    """分析是否可以自然地在回复中提及marathon100 app"""
    title_lower = post_title.lower()
    content_lower = post_content.lower()
    combined_text = title_lower + " " + content_lower
    
    # 高相关性subreddit列表
    high_relevance_subs = ["running", "marathon", "marathontraining", "firstmarathon", "C25K", 
                          "loseit", "fitness", "progresspics"]
    
    # 关键词检测
    has_tracking_keywords = any(kw in combined_text for kw in TRACKING_KEYWORDS)
    has_app_request = any(kw in combined_text for kw in APP_REQUEST_KEYWORDS)
    has_plan_keywords = any(kw in combined_text for kw in PLAN_KEYWORDS)
    
    # 检查是否包含负面提及或竞争对手app
    negative_mentions = ["hate apps", "don't use apps", "apps don't work"]
    competitor_apps = ["strava", "nike run club", "runkeeper", "garmin"]
    has_negative = any(neg in combined_text for neg in negative_mentions)
    
    # 获取当前app提及概率调整因子
    probability_boost = adjust_app_mention_probability()
    
    # 如果是直接请求app推荐或高度相关的subreddit讨论训练计划，返回True
    if has_app_request or (subreddit in high_relevance_subs and (has_tracking_keywords or has_plan_keywords)):
        if not has_negative:
            return True
    
    # 如果是在讨论竞争对手的app，有更高的机会自然提及
    if any(comp in combined_text for comp in competitor_apps):
        return random.random() < (0.3 + probability_boost)
    
    # 在与跑步和健身相关的subreddit中，有更高概率提及
    if subreddit in high_relevance_subs:
        return random.random() < (0.15 + probability_boost)
    
    # 在其他subreddit中，有较低概率提及
    return random.random() < (0.05 + probability_boost)

# === 动态调整app提及概率 ===
def adjust_app_mention_probability():
    """根据当前进度动态调整app提及概率"""
    current_time = datetime.now()
    hours_passed = current_time.hour + current_time.minute/60
    day_progress = min(1.0, hours_passed / 16)  # 假设16小时活跃时间
    
    # 计算目标进度
    target_mentions = 30
    expected_mentions_by_now = target_mentions * day_progress
    
    # 如果落后于预期，增加提及概率
    if app_mentions_today < expected_mentions_by_now:
        # 当前进度与预期进度的差距
        mention_deficit = expected_mentions_by_now - app_mentions_today
        # 提高提及概率（最多增加30%）
        increase_factor = min(0.3, mention_deficit / 10)
        log(f"📊 App提及进度落后，提高提及概率 +{increase_factor:.2f}")
        return increase_factor
    return 0.0

# === 重置每日计数器 ===
def reset_daily_counters():
    global comment_count, app_mentions_today, last_reset_date, last_app_mention_reset
    
    current_date = datetime.now().date()
    if current_date != last_reset_date:
        log(f"🔄 新的一天 ({current_date})，评论计数器已重置")
        log(f"📊 昨日APP提及总数: {app_mentions_today}")
        comment_count = 0
        app_mentions_today = 0
        last_reset_date = current_date
        last_app_mention_reset = current_date

# === 保存评论日志 ===
def log_comment(subreddit, post_title, comment, mentioned_app=False):
    global app_mentions_count, app_mentions_today
    
    if mentioned_app:
        app_mentions_count += 1
        app_mentions_today += 1
    
    try:
        with open(comment_log_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().isoformat()
            app_mention_tag = "[APP MENTION] " if mentioned_app else ""
            f.write(f"[{timestamp}] {app_mention_tag}r/{subreddit} - {post_title}\nComment: {comment}\n\n---\n\n")
        log(f"📝 评论已记录到 {comment_log_file}" + (f" (包含APP提及! 今日第{app_mentions_today}次)" if mentioned_app else ""))
    except Exception as e:
        log(f"⚠️ 警告: 写入评论日志文件失败: {str(e)}", error=True)

# === GPT 生成发帖内容 ===
def generate_post():
    log(f"🧠 为r/{TARGET_SUBREDDIT}生成帖子内容...")
    
    # 获取与当前时间相符的训练情境
    time_context = get_training_time_context()
    
    # 准备最近帖子的摘要
    recent_posts_summary = ""
    if post_history:
        # 最多包含最近3天的历史
        for recent_post in post_history[-3:]:
            day = recent_post["day"]
            # 摘取帖子正文的前100个字符作为摘要
            body_snippet = recent_post["body"][:100].replace("\n", " ") + "..."
            recent_posts_summary += f"- Day {day}: {body_snippet}\n"
    
    prompt = f"""
You are Patrick — a positive, slightly humorous, energetic running coach currently on day {patrick_state['day']} of a 100-day marathon training challenge.
You've currently run about {patrick_state['total_km']} km total.
You're feeling {patrick_state['mood']}, and struggling with things like {', '.join(patrick_state['struggles'])}.
You're sharing your reflections and thoughts on Reddit in r/{TARGET_SUBREDDIT}.

Based on the current time of day, your latest run was {time_context["when"]} in the {time_context["time_desc"]}. 
Details about your run timing: {time_context["details"]}

Here are summaries of your most recent posts to maintain continuity:
{recent_posts_summary}

Full text of your most recent post (Day {post_history[-1]['day']}):
{post_history[-1]['body']}

Write a Reddit post for Day {patrick_state['day']} that:
- Is from Patrick, staying consistent with his background
- Has a title and a body (formatted clearly)
- Feels personal and real
- References your most recent run which happened {time_context["when"]}
- References things mentioned in your previous posts for continuity
- Shows progression in your running journey
- Invites interaction
- Avoids promotion and links
- Is 100–200 words
- For C25K community, shows understanding of beginner runners facing the couch-to-5k challenge, while still maintaining your marathon training journey
- Offers encouragement that relates to both your journey and theirs

Output format:
Title: ...
Body: ...
"""
    try:
        # 使用OpenAI API v1.0.0+
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        text = response.choices[0].message.content
        lines = text.strip().split("\n")
        title = ""
        body_lines = []
        for line in lines:
            if line.lower().startswith("title:"):
                title = line.replace("Title:", "").strip()
            elif line.lower().startswith("body:"):
                continue
            else:
                body_lines.append(line)
        body = "\n".join(body_lines)
        log(f"✅ 帖子内容已生成: '{title}'")
        
        # 更新帖子历史
        update_post_history(patrick_state["day"], title, body)
        
        return title, body
    except Exception as e:
        log(f"❌ OpenAI API错误: {str(e)}", error=True)
        log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
        raise

# === GPT 生成评论内容 ===
def generate_comment(title, content, subreddit_name):
    """根据不同的subreddit生成适合的评论内容"""
    log(f"🧠 为r/{subreddit_name}生成评论内容...")
    
    # 检查是否可以自然提及app
    should_mention_app = can_naturally_mention_app(title, content, subreddit_name)
    app_instruction = ""
    
    if should_mention_app:
        app_instruction = """
        As part of your response, find a natural way to briefly mention that you've been using an app called marathon100 (all lowercase) to track your running progress. 
        Do not be promotional or overly enthusiastic - just casually mention it as something you personally use. 
        The mention should be seamlessly integrated into your response, not standing out as an advertisement.
        Examples of natural mentions:
        - "I track my runs with marathon100 and it's been helpful."
        - "Setting up a schedule in marathon100 has worked for me."
        - "I use marathon100 to log my training."
        """
    
    # 通用的简短回复指导
    brevity_instruction = """
    Your response must be between 20-80 words total (approximately 100-400 characters). Keep it brief and to the point.
    Avoid being overly enthusiastic or using exclamation points.
    Use a casual, conversational tone that's helpful but not excessively eager or emotional.
    """
    
    # 根据不同的 subreddit 调整 prompt
    if subreddit_name.lower() in ["running", "marathon", "marathontraining", "firstmarathon", "c25k"]:
        prompt = f"""
        You're responding to this post on r/{subreddit_name}:
        Title: {title}
        Content: {content}

        Write a brief, casual comment as Patrick, who's training for a marathon. Your comment should:
        1. Provide one specific, practical tip or insight
        2. Sound like a real Reddit user, not generic advice
        
        {app_instruction}
        {brevity_instruction}
        """
    elif subreddit_name.lower() in ["fitness", "loseit", "progresspics", "bodyweightfitness", "xxfitness"]:
        prompt = f"""
        You're responding to this post on r/{subreddit_name}:
        Title: {title}
        Content: {content}

        Write a brief comment as Patrick, a runner training for a marathon. Your comment should:
        1. Relate to the person's fitness journey with a single insight
        2. Be supportive but not overly enthusiastic
        
        {app_instruction}
        {brevity_instruction}
        """
    elif subreddit_name.lower() in ["healthyfood", "intermittentfasting"]:
        prompt = f"""
        You're responding to this post on r/{subreddit_name}:
        Title: {title}
        Content: {content}

        Write a brief comment as Patrick, who's training for a marathon. Your comment should:
        1. Connect nutrition to running with a single practical point
        2. Be casual and conversational, not preachy
        
        {app_instruction}
        {brevity_instruction}
        """
    elif subreddit_name.lower() in ["getdisciplined", "selfimprovement", "productivity", "decidingtobebetter"]:
        prompt = f"""
        You're responding to this post on r/{subreddit_name}:
        Title: {title}
        Content: {content}

        Write a brief comment as Patrick, who's building discipline through marathon training. Your comment should:
        1. Offer one practical habit-building tip from your experience
        2. Be matter-of-fact and not overly motivational
        
        {app_instruction}
        {brevity_instruction}
        """
    elif subreddit_name.lower() in ["quantifiedself", "applewatch", "technology", "gadgets"]:
        prompt = f"""
        You're responding to this post on r/{subreddit_name}:
        Title: {title}
        Content: {content}

        Write a brief comment as Patrick, who uses tech for running. Your comment should:
        1. Share one specific tech use case for your training
        2. Be straightforward and conversational
        
        {app_instruction}
        {brevity_instruction}
        """
    elif subreddit_name.lower() == "askreddit":
        prompt = f"""
        You're responding to this AskReddit post:
        Title: {title}
        Content: {content}

        Write a brief comment that subtly mentions you're a runner. Your comment should:
        1. Answer the question directly and concisely
        2. Be casual and conversational
        
        {app_instruction}
        {brevity_instruction}
        """
    else:  # 其他所有subreddit的通用prompt
        prompt = f"""
        You're responding to this post on r/{subreddit_name}:
        Title: {title}
        Content: {content}

        Write a brief comment as Patrick, who's training for a marathon. Your comment should:
        1. Be directly relevant to the post topic
        2. Offer one specific insight or tip
        3. Be conversational and casual, not overly enthusiastic
        
        {app_instruction}
        {brevity_instruction}
        """

    try:
        # 使用OpenAI API v1.0.0+
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,  # 限制token数量以确保简短回复
        )
        comment_text = response.choices[0].message.content.strip()
        log(f"✅ 评论内容已生成: '{comment_text[:50]}...'")
        return comment_text, should_mention_app
    except Exception as e:
        log(f"❌ OpenAI API错误: {str(e)}", error=True)
        log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
        raise

# === 保存发帖日志 ===
def log_post(title, body):
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            uk_time = get_uk_time().isoformat()
            f.write(f"[{uk_time}] r/{TARGET_SUBREDDIT}\nTitle: {title}\nBody:\n{body}\n\n---\n\n")
        log(f"📝 帖子已记录到 {log_file}")
    except Exception as e:
        log(f"⚠️ 警告: 写入日志文件失败: {str(e)}", error=True)

# === 获取子版块的可用 flair ===
def get_available_flairs():
    """尝试获取subreddit的可用flairs并记录"""
    try:
        subreddit = reddit.subreddit(TARGET_SUBREDDIT)
        flairs = list(subreddit.flair.link_templates.user_selectable())
        log(f"📋 r/{TARGET_SUBREDDIT}的可用flairs: 找到{len(flairs)}个")
        
        # 记录可用的flairs以供参考
        for flair in flairs[:5]:  # 限制为前5个以避免日志过多
            flair_id = flair["id"] if "id" in flair else "未知"
            flair_text = flair["text"] if "text" in flair else "未知"
            log(f"   - Flair: '{flair_text}' (ID: {flair_id})")
        
        if len(flairs) > 5:
            log(f"   - ... 以及另外 {len(flairs) - 5} 个flairs")
            
        return flairs
    except Exception as e:
        log(f"⚠️ 警告: 无法获取r/{TARGET_SUBREDDIT}的flairs: {str(e)}", error=True)
        # 如果获得403错误，说明我们没有权限获取flairs
        if "403" in str(e):
            log(f"ℹ️ 将为r/{TARGET_SUBREDDIT}使用直接flair分配")
        return []

# === 发帖函数 ===
def post_to_subreddit():
    log(f"🚀 尝试在r/{TARGET_SUBREDDIT}发帖...")
    try:
        # 获取当前时间上下文
        time_context = get_training_time_context()
        log(f"⏰ 当前时间段上下文: 跑步时间为{time_context['when']}")
        
        title, body = generate_post()
        subreddit = reddit.subreddit(TARGET_SUBREDDIT)
        
        # 获取flair配置
        flair_config = SUBREDDITS_CONFIG.get(TARGET_SUBREDDIT, {})
        flair_id = flair_config.get("flair_id")
        flair_text = flair_config.get("flair_text")
        
        # 如果没有配置flair但可能需要，尝试获取可用的flairs
        if not flair_id and not flair_text:
            flairs = get_available_flairs()
            if flairs:
                flair = flairs[0]
                flair_id = flair.get("id")
                flair_text = flair.get("text")
                log(f"📌 自动选择flair: '{flair_text}'")
        
        # 如果有flair则使用
        if flair_id or flair_text:
            log(f"📌 使用flair: ID={flair_id}, Text='{flair_text}'")
            submission = subreddit.submit(title, selftext=body, flair_id=flair_id, flair_text=flair_text)
        else:
            log(f"ℹ️ 没有flair配置，发帖时不使用flair")
            submission = subreddit.submit(title, selftext=body)
            
        log(f"✅ 成功发帖到r/{TARGET_SUBREDDIT}: {submission.url}")
        log_post(title, body)
        
        # 更新最后发帖日期为今天（英国时区）
        global last_post_date
        last_post_date = get_uk_time().date()
        
        return submission
    except Exception as e:
        log(f"❌ 发帖到r/{TARGET_SUBREDDIT}出错: {str(e)}", error=True)
        log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
        raise

# === 计算评论间隔 ===
def calculate_comment_interval():
    """计算下一条评论的最佳间隔时间"""
    current_date = datetime.now().date()
    current_time = datetime.now()
    
    # 计算当天可用时间范围（假设机器人活跃时间为16小时）
    active_hours = 16
    seconds_available = active_hours * 3600
    
    # 计算确保达到每日最低目标所需的评论速度
    comments_needed = MIN_DAILY_COMMENTS - comment_count
    if comments_needed > 0 and seconds_available > 0:
        required_interval_seconds = seconds_available / comments_needed
        # 使用动态间隔，但不低于2分钟，不高于8分钟
        actual_interval_seconds = max(120, min(480, required_interval_seconds))
        # 添加一些随机性，避免固定模式
        actual_interval_seconds = actual_interval_seconds * random.uniform(0.8, 1.2)
    else:
        actual_interval_seconds = INTERVAL_BETWEEN_COMMENTS * 60
    
    return actual_interval_seconds

# === 评论函数 ===
def post_comment(specific_subreddit=None):
    global comment_count, last_comment_time, last_reset_date
    
    # 重置评论计数器(如果是新的一天)
    reset_daily_counters()
    
    # 检查是否达到每日上限
    if comment_count >= MAX_DAILY_COMMENTS:
        log(f"⛔️ 已达到每日评论上限 ({MAX_DAILY_COMMENTS})，今天不再评论")
        return False
    
    # 为不同的subreddit设置权重，优先考虑相关度高的subreddit和高karma的subreddit
    sub_weights = {
        # 高优先级 (权重 5)
        "running": 5,
        "marathon": 5,
        "marathontraining": 5,
        "firstmarathon": 5,
        "C25K": 5,
        "loseit": 5,
        "fitness": 5,
        "progresspics": 5,
        
        # 中等优先级 (权重 3)
        "bodyweightfitness": 3,
        "xxfitness": 3,
        "HealthyFood": 3,
        "intermittentfasting": 3,
        "getdisciplined": 3,
        "selfimprovement": 3,
        "productivity": 3,
        "decidingtobebetter": 3,
        "QuantifiedSelf": 3,
        "AppleWatch": 3,
        
        # 低优先级但高karma潜力 (权重 4)
        "AskReddit": 4,
        
        # 低优先级 (权重 2)
        "NoStupidQuestions": 2,
        "LifeProTips": 2,
        "simpleliving": 2,
        "gadgets": 2,
        "technology": 2
    }
    
    # 如果指定了subreddit，则直接使用该subreddit
    if specific_subreddit:
        sub = specific_subreddit
        log(f"🔍 检查指定的r/{sub}...")
    else:
        # 加权随机选择subreddit
        sub_items = list(sub_weights.items())
        sub_names = [item[0] for item in sub_items]
        sub_weights_values = [item[1] for item in sub_items]
        
        sub = random.choices(sub_names, weights=sub_weights_values, k=1)[0]
        log(f"🔍 随机选择r/{sub} (权重: {sub_weights.get(sub, 1)})...")
    
    subreddit = reddit.subreddit(sub)
    posts_checked = 0
    comment_posted = False
    
    # 为不同类型的 subreddit 使用不同的浏览策略
    if sub.lower() in ["askreddit", "nostupidquestions", "lifeprotips"]:
        # 对高karma潜力的subreddit，优先查看热门和上升中的帖子
        posts_to_check = []
        
        # 获取热门帖子
        hot_posts = list(subreddit.hot(limit=5))
        rising_posts = list(subreddit.rising(limit=5))
        new_posts = list(subreddit.new(limit=5))
        
        posts_to_check.extend(hot_posts)
        posts_to_check.extend(rising_posts)
        posts_to_check.extend(new_posts)
        
        # 随机打乱顺序，避免总是评论同类型帖子
        random.shuffle(posts_to_check)
        
        for post in posts_to_check:
            posts_checked += 1
            
            # 对大型subreddit优先评论热门帖子，提高karma获取几率
            if post.id not in commented_ids and post.score > 10:
                try:
                    log(f"📝 正在为r/{sub}的帖子生成评论: {post.title}")
                    comment_text, mentioned_app = generate_comment(post.title, post.selftext, sub)
                    log(f"💬 评论: {comment_text[:50]}...")
                    
                    post.reply(comment_text)
                    commented_ids.add(post.id)
                    comment_count += 1
                    last_comment_time = time.time()
                    log(f"✅ 已在r/{sub}发表评论。今日总计: {comment_count}/{MIN_DAILY_COMMENTS}")
                    log_comment(sub, post.title, comment_text, mentioned_app)
                    comment_posted = True
                    break
                except Exception as e:
                    log(f"❌ 在r/{sub}发表评论时出错: {str(e)}", error=True)
    else:
        # 对相关性高的subreddit使用关键词筛选
        posts_to_check = []
        
        # 取新帖和热门帖，增加匹配几率
        new_posts = list(subreddit.new(limit=7))
        hot_posts = list(subreddit.hot(limit=7))
        
        posts_to_check.extend(new_posts)
        posts_to_check.extend(hot_posts)
        
        # 对列表进行洗牌
        random.shuffle(posts_to_check)
        
        for post in posts_to_check:
            posts_checked += 1
            
            if post.id in commented_ids:
                continue
                
            if any(k.lower() in post.title.lower() for k in KEYWORDS):
                try:
                    log(f"📝 正在为r/{sub}的帖子生成评论: {post.title}")
                    comment_text, mentioned_app = generate_comment(post.title, post.selftext, sub)
                    log(f"💬 评论: {comment_text[:50]}...")
                    
                    post.reply(comment_text)
                    commented_ids.add(post.id)
                    comment_count += 1
                    last_comment_time = time.time()
                    log(f"✅ 已在r/{sub}发表评论。今日总计: {comment_count}/{MIN_DAILY_COMMENTS}")
                    log_comment(sub, post.title, comment_text, mentioned_app)
                    comment_posted = True
                    break
                except Exception as e:
                    log(f"❌ 在r/{sub}发表评论时出错: {str(e)}", error=True)
    
    log(f"👀 已检查r/{sub}中的{posts_checked}个帖子" + (", 找到匹配项!" if comment_posted else ", 未找到合适的帖子."))
    return comment_posted

# === 并行处理多个评论队列 ===
def process_multiple_comments():
    """并行处理多个评论队列以提高效率"""
    # 从权重高的subreddit中随机选择3-5个
    weighted_subs = []
    for sub, weight in sub_weights.items():
        weighted_subs.extend([sub] * weight)
    
    num_to_check = min(3, len(weighted_subs))
    selected_subs = random.sample(weighted_subs, num_to_check)
    
    comments_made = 0
    
    # 为每个选定的subreddit尝试发表评论
    for sub in selected_subs:
        if post_comment(sub):
            comments_made += 1
            # 休息随机时间避免API限制
            time.sleep(random.uniform(20, 40))
    
    return comments_made > 0

# === 健康检查 ===
def health_check():
    """执行定期健康检查以确认脚本仍在正常运行"""
    try:
        # 检查Reddit连接
        username = reddit.user.me().name
        uk_time = get_uk_time().strftime("%H:%M:%S")
        log(f"💓 健康检查: Reddit API连接正常 (用户: {username}), 英国当前时间: {uk_time}")
        
        # 记录Patrick的当前状态
        log(f"💓 健康: Patrick在第{patrick_state['day']}天, 已跑{patrick_state['total_km']}公里, 感觉{patrick_state['mood']}")
        
        # 记录评论状态
        log(f"💓 评论状态: 今日已发表{comment_count}/{MIN_DAILY_COMMENTS}条评论")
        
        # 记录App提及状态
        log(f"💓 App提及: 今日已提及{app_mentions_today}/30次, 总计已提及{app_mentions_count}次")
        
        return True
    except Exception as e:
        log(f"⚠️ 健康检查失败: {str(e)}", error=True)
        return False

# === 启动时获取子版块信息 ===
def initialize_subreddit_info():
    log("🔍 获取subreddit信息...")
    try:
        # 验证我们可以访问subreddit
        subreddit = reddit.subreddit(TARGET_SUBREDDIT)
        
        # 获取subreddit规则以检查发帖要求
        try:
            rules = list(subreddit.rules)
            log(f"📋 r/{TARGET_SUBREDDIT}: 找到{len(rules)}条规则")
            
            # 检查规则中是否提到flair要求
            flair_required = any("flair" in rule.description.lower() for rule in rules if hasattr(rule, 'description'))
            if flair_required:
                log(f"⚠️ r/{TARGET_SUBREDDIT}可能需要flair（根据规则）")
        except Exception as e:
            log(f"⚠️ 无法获取r/{TARGET_SUBREDDIT}的规则: {str(e)}", error=True)
        
        # 尝试获取flairs
        get_available_flairs()
        
    except Exception as e:
        log(f"⚠️ 无法初始化r/{TARGET_SUBREDDIT}的信息: {str(e)}", error=True)

# === 主循环 ===
def main_loop():
    """主应用循环，提取为函数以便更好地处理错误"""
    global last_comment_time, comment_count, last_reset_date
    
    health_check_interval = 60 * 30  # 每30分钟检查一次健康状况
    post_check_interval = 60 * 15    # 每15分钟检查一次是否需要发帖
    comment_check_interval = 60 * 2  # 每2分钟检查一次是否需要评论
    
    last_health_check = get_uk_time()
    last_post_check = get_uk_time()
    last_comment_check = datetime.now()
    
    # 初始化评论计数和日期
    last_reset_date = datetime.now().date()
    
    while True:
        try:
            now = get_uk_time()
            current_time = datetime.now()
            
            # 定期健康检查
            if (now - last_health_check).total_seconds() >= health_check_interval:
                health_check()
                last_health_check = now
            
            # 检查是否需要发帖
            if (now - last_post_check).total_seconds() >= post_check_interval:
                log("🔍 检查是否需要发帖...")
                last_post_check = now
                
                # 检查今天是否已经发过帖子
                if should_post_today():
                    # 检查当前是否在发帖时间窗口内
                    if is_posting_time():
                        try:
                            # 尝试发帖
                            post_to_subreddit()
                            
                            # 更新Patrick状态
                            km_run = random.randint(4, 10)
                            patrick_state["day"] += 1
                            patrick_state["total_km"] += km_run
                            log(f"🏃 Patrick前进到第{patrick_state['day']}天并跑了+{km_run}公里")
                            
                            # 每7天切换一次情绪和挑战
                            mood_index = ((patrick_state["day"] - 1) // 7) % len(mood_cycle)
                            patrick_state["mood"], patrick_state["struggles"] = mood_cycle[mood_index]
                            log(f"😊 Patrick的情绪更新为: {patrick_state['mood']}")
                        except Exception as e:
                            log(f"❌ 发帖到r/{TARGET_SUBREDDIT}失败: {str(e)}", error=True)
                            log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
                            # 将在下次检查时再次尝试
                    else:
                        log("⏰ 当前不在发帖时间窗口内 (UK 11:00-20:00)，等待合适时间")
            
            # 检查是否需要评论
            if (current_time - last_comment_check).total_seconds() >= comment_check_interval:
                log("🔍 检查是否需要发表评论...")
                last_comment_check = current_time
                
                # 检查今天的评论数是否已达到上限
                if comment_count >= MAX_DAILY_COMMENTS:
                    log(f"⛔️ 已达到每日评论上限 ({MAX_DAILY_COMMENTS})，今天不再评论")
                else:
                    # 检查是否需要等待上一条评论的间隔时间
                    if last_comment_time:
                        ideal_interval = calculate_comment_interval()
                        time_since_last_comment = time.time() - last_comment_time
                        if time_since_last_comment < ideal_interval:
                            wait_time = int(ideal_interval - time_since_last_comment)
                            log(f"🕒 距离下一条评论还需等待 {wait_time} 秒...")
                        else:
                            # 尝试发表评论
                            try:
                                post_comment()
                            except Exception as e:
                                log(f"❌ 发表评论失败: {str(e)}", error=True)
                                log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
                    else:
                        # 第一次评论，直接发表
                        try:
                            post_comment()
                        except Exception as e:
                            log(f"❌ 发表评论失败: {str(e)}", error=True)
                            log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
            
            # 监控App提及进度
            if app_mentions_today < 30 and comment_count > 50:
                log(f"📊 App提及进度检查: 已提及{app_mentions_today}/30次, 已评论{comment_count}次")
                # 如果已经评论了一半但App提及不到一半，增加提及频率
                if app_mentions_today < 15:
                    log(f"⚠️ App提及进度落后, 提高提及频率")
            
            # 计算发帖状态信息
            uk_now = get_uk_time()
            
            # 计算到下一个发帖窗口的时间
            next_window_time = None
            if uk_now.hour < 11:
                # 当前时间早于11点，等到今天11点
                next_window_time = uk_now.replace(hour=11, minute=0, second=0, microsecond=0)
            elif uk_now.hour >= 20:
                # 当前时间晚于20点，等到明天11点
                next_window_time = (uk_now + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
            
            # 如果今天已发帖，计算到明天11点的时间
            if last_post_date == uk_now.date():
                next_window_time = (uk_now + timedelta(days=1)).replace(hour=11, minute=0, second=0, microsecond=0)
                wait_seconds = (next_window_time - uk_now).total_seconds()
                wait_hours = wait_seconds / 3600
                log(f"⏳ 今天已完成发帖。距离下一个发帖窗口（明天UK 11:00）还有{wait_hours:.1f}小时")
            elif next_window_time:
                # 如果不在发帖窗口内，显示到下一个窗口的时间
                wait_seconds = (next_window_time - uk_now).total_seconds()
                wait_hours = wait_seconds / 3600
                log(f"⏳ 距离下一个发帖窗口（UK {next_window_time.strftime('%H:%M')}）还有{wait_hours:.1f}小时")
            else:
                # 在发帖窗口内但尚未发帖
                window_end = uk_now.replace(hour=20, minute=0, second=0, microsecond=0)
                remaining_seconds = (window_end - uk_now).total_seconds()
                remaining_hours = remaining_seconds / 3600
                log(f"⏳ 当前在发帖窗口内，尚未完成今日发帖。发帖窗口还剩{remaining_hours:.1f}小时结束")
            
            # 计算评论状态信息
            comments_left = MIN_DAILY_COMMENTS - comment_count
            if comments_left > 0:
                log(f"⏳ 今日还需发表 {comments_left} 条评论以达到最低目标")
            else:
                log(f"✅ 今日评论最低目标已达成! 已发表 {comment_count}/{MIN_DAILY_COMMENTS} 条评论")
            
            # 休眠适当时间
            time.sleep(60 * 1)  # 1分钟检查一次状态
                
        except KeyboardInterrupt:
            log("👋 脚本被手动停止（键盘中断）")
            break
        except Exception as e:
            log(f"‼️ 主循环中意外错误: {str(e)}", error=True)
            log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
            log("🔄 错误后继续主循环")
            time.sleep(60 * 5)  # 错误后等待5分钟再继续

# === 脚本启动入口 ===
if __name__ == "__main__":
    log("🚀 Reddit多功能机器人启动！")
    log(f"🌐 发帖配置: 仅发布到r/{TARGET_SUBREDDIT}, 英国时区, 每天一帖")
    log(f"⏰ 发帖时间窗口: 英国时间 11:00-20:00")
    log(f"📊 Patrick当前状态: 第{patrick_state['day']}天, 已跑{patrick_state['total_km']}公里")
    log(f"🧠 已加载历史帖子记录: {len(post_history)}个")
    log(f"💬 评论配置: 目标每日{MIN_DAILY_COMMENTS}-{MAX_DAILY_COMMENTS}条评论")
    log(f"🎯 评论目标社区: {', '.join(['r/' + sub for sub in COMMENT_SUBREDDITS[:5]])}等{len(COMMENT_SUBREDDITS)}个社区")
    log(f"📱 目标App提及: 每天至少30次")

    # 在启动时初始化subreddit信息
    try:
        initialize_subreddit_info()
        
        # 开始主循环
        main_loop()
    except Exception as e:
        log(f"💥 致命错误: {str(e)}", error=True)
        log(f"堆栈跟踪: {traceback.format_exc()}", error=True)
        log("⛔ 脚本因不可恢复的错误而终止")



        
