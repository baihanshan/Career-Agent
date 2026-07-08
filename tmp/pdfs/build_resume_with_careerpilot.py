from __future__ import annotations

from pathlib import Path

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "output/pdf/叶飞_CareerPilot_Agent_简历.pdf"
ORIGINAL_RENDER = ROOT / "tmp/pdfs/original_resume-1.png"
PORTRAIT = ROOT / "tmp/pdfs/portrait_crop.png"

FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
pdfmetrics.registerFont(TTFont("ArialUnicode", str(FONT_PATH)))

FONT = "ArialUnicode"
PAGE_W, PAGE_H = A4
LEFT = 36
RIGHT = 36
TOP = 42
BOTTOM = 28
LINE = 11.7


def crop_portrait() -> None:
    if PORTRAIT.exists():
        return
    img = Image.open(ORIGINAL_RENDER)
    # Crop the portrait from the rendered original resume.
    crop = img.crop((1072, 42, 1235, 232))
    crop.save(PORTRAIT)


def text_width(text: str, size: float) -> float:
    return pdfmetrics.stringWidth(text, FONT, size)


def wrap_text(text: str, size: float, max_width: float) -> list[str]:
    lines: list[str] = []
    current = ""
    closing_punctuation = "。，；：、！？,.!?;:)"
    for ch in text:
        trial = current + ch
        if text_width(trial, size) <= max_width:
            current = trial
            continue
        if current and ch in closing_punctuation:
            current = trial
            continue
        if current:
            lines.append(current)
        current = ch
    if current:
        lines.append(current)
    return lines


def draw_text(c: canvas.Canvas, x: float, y: float, text: str, size: float = 8.4) -> None:
    c.setFont(FONT, size)
    c.drawString(x, y, text)


def draw_bold(c: canvas.Canvas, x: float, y: float, text: str, size: float = 8.4) -> None:
    # STSong-Light has no true bold in reportlab CID mode, so draw twice with a tiny offset.
    c.setFont(FONT, size)
    c.drawString(x, y, text)
    c.drawString(x + 0.18, y, text)


def section(c: canvas.Canvas, y: float, title: str) -> float:
    c.setLineWidth(0.9)
    c.line(LEFT, y + 10, PAGE_W - RIGHT, y + 10)
    draw_bold(c, LEFT, y, title, 12)
    return y - 15


def paragraph(c: canvas.Canvas, x: float, y: float, text: str, size: float, width: float, leading: float) -> float:
    for line in wrap_text(text, size, width):
        draw_text(c, x, y, line, size)
        y -= leading
    return y


def bullet(c: canvas.Canvas, y: float, text: str, width: float | None = None) -> float:
    width = width or PAGE_W - LEFT - RIGHT - 8
    return paragraph(c, LEFT, y, "- " + text, 7.35, width, 10.6)


def project(c: canvas.Canvas, y: float, role: str, name: str, date: str, bullets: list[str]) -> float:
    draw_bold(c, LEFT, y, role, 8.2)
    draw_bold(c, LEFT + 178, y, name, 8.2)
    draw_bold(c, PAGE_W - RIGHT - text_width(date, 8.2), y, date, 8.2)
    y -= 11.5
    for item in bullets:
        y = bullet(c, y, item)
    return y - 2


def internship(c: canvas.Canvas, y: float) -> float:
    draw_bold(c, LEFT, y, "人工智能实习生", 8.2)
    draw_bold(c, LEFT + 198, y, "腾讯混元部门多模态团队，中国深圳", 8.2)
    draw_bold(c, PAGE_W - RIGHT - text_width("2024 年 12 月-2025 年 1 月", 8.2), y, "2024 年 12 月-2025 年 1 月", 8.2)
    y -= 11.5
    items = [
        "设计图像转文本模型智能评估流程，调用成熟大语言模型作为评审器，将图生文输出与原始图像联合输入并自动判断生成错误。",
        "梳理图像转文本常见故障类型，并将评审结果与人工标注 ground truth 对比，结合混淆矩阵与性能指标形成评估报告，支持核心模型改进决策。",
    ]
    for item in items:
        y = bullet(c, y, item)
    return y - 1


def build() -> None:
    crop_portrait()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(OUT), pagesize=A4)

    y = PAGE_H - TOP
    draw_bold(c, LEFT, y, "叶飞", 18)
    c.drawImage(ImageReader(str(PORTRAIT)), PAGE_W - RIGHT - 68, PAGE_H - TOP - 37, 68, 78, preserveAspectRatio=True, mask="auto")
    y -= 25
    draw_text(c, LEFT, y, "浙江宁波  |  +86 18268649597  |  yefuqing00@163.com  |  党员  |  应届生", 8.7)
    y -= 16
    draw_bold(c, LEFT, y, "求职意向：AI 工程师/算法工程师", 9.2)

    y = section(c, y - 22, "教育经历")
    draw_bold(c, LEFT, y, "新南威尔士大学（UNSW，全球 QS19）", 8.5)
    draw_bold(c, LEFT + 176, y, "2024 年 2 月-2025 年 10 月", 8.5)
    draw_bold(c, LEFT + 318, y, "浙江工业大学", 8.5)
    draw_bold(c, PAGE_W - RIGHT - text_width("2019 年 9 月-2023 年 6 月", 8.5), y, "2019 年 9 月-2023 年 6 月", 8.5)
    y -= 13
    draw_text(c, LEFT, y, "人工智能专业，硕士", 8.2)
    draw_text(c, LEFT + 318, y, "软件工程专业，本科", 8.2)
    y -= 13
    draw_text(c, LEFT, y, "WAM：82（前 10%）", 8.2)
    draw_text(c, LEFT + 318, y, "GPA：3.3", 8.2)

    y = section(c, y - 14, "项目经历")
    y = project(
        c,
        y,
        "项目负责人/全栈开发",
        "CareerPilot Agent：求职材料 Agentic LLM 应用",
        "2026 年 6 月 - 2026 年 7 月",
        [
            "独立设计并实现面向求职者的 AI 求职助手，用户输入个人材料与目标 JD 后，系统生成岗位匹配摘要、3 条证据支撑简历要点、面试准备和风险提示。",
            "采用 FastAPI、Next.js、Pydantic 与 LangGraph 搭建前后端和固定主流程，覆盖输入解析、简历索引、JD 分析、证据检索、内容生成、风险审计和公开输出。",
            "实现局部 ReAct 多 Agent 架构：简历证据 Agent 通过工具检索材料，面试准备 Agent 区分 JD 能力考察与简历深挖，风险审计 Agent 进行岗位类型感知复核。",
            "接入 BGE embedding 与 Chroma 向量库，按项目/实习/技能/教育结构化切分简历；通过 Public Output Gate、证据 ID 规范化和质量门禁防止内部 ID 泄露与生成内容失真。",
        ],
    )
    y = project(
        c,
        y,
        "Scrum Master",
        "使用大语言模型识别并分类隐性性别歧视",
        "2025 年 5 月 - 2025 年 8 月",
        [
            "由学校客户发起，构建基于大语言模型的多智能体与 RAG 检索增强系统，负责敏捷协作、Agent 架构设计和核心工具链落地。",
            "设计男性/女性视角 Agent + 裁判 Agent 的多视角推理与投票机制，结合 SentenceTransformers + HNSWlib 实现 few-shot 样例召回与证据对齐。",
            "融合 RAG、标注准则、Chain-of-Thought 与 Self-Reflection 优化 prompt，在 3,242 条语料上实现 64.93% 三分类准确率，优于基线模型。",
        ],
    )
    y = project(
        c,
        y,
        "项目负责人",
        "自然环境中的语义分割",
        "2024 年 2 月 - 2024 年 6 月",
        [
            "基于 DeepLabV3+ 搭建端到端语义分割实验平台，面向 WildScenes 数据集解决自然环境中目标边界模糊与场景多样性问题。",
            "改进解码器，引入多尺度特征融合与轻量级通道注意力模块，对 ASPP 不同膨胀率特征加权融合；平均 IoU 提升 17%，整体精度较基线提升 14%。",
        ],
    )
    y = project(
        c,
        y,
        "项目负责人",
        "客户反馈自动分类系统",
        "2025 年 1 月 - 2025 年 5 月",
        [
            "构建基于 NLP 特征提取的客户反馈自动分类系统，将用户反馈映射至 28 个产品部门；结合 Permutation Importance 与 Pearson 相关性进行特征选择。",
            "采用 SMOTE、类别加权与 KS/KL 散度检测处理类不平衡和分布偏移，最终 XGBoost 达到 AUC-ROC 0.957、F1-score 0.693。",
        ],
    )

    y = section(c, y - 2, "实习经历")
    y = internship(c, y)

    y = section(c, y - 2, "技能")
    for item in [
        "熟练掌握 Python，熟悉 NumPy、Pandas、Scikit-learn、PyTorch 等工具，具备 C++ 与 Java 编程基础。",
        "熟悉 LangChain、LangGraph、RAG、Prompt Engineering、ReAct Agent、向量检索、Chroma、FastAPI、Next.js、Docker、Git。",
        "语言：雅思 6.5，英语六级，有国外高校学术汇报和项目展示经验，具备中英文双语沟通能力。",
    ]:
        y = bullet(c, y, item)

    y = section(c, y - 1, "奖项")
    for item in [
        "2021 年浙江工业大学“双百双进”暑期社会实践暨思想政治理论课实践教学活动优秀调研课题三等奖。",
        "浙江工业大学校三等学习奖学金。",
    ]:
        y = bullet(c, y, item)

    c.save()
    print(OUT)


if __name__ == "__main__":
    build()
