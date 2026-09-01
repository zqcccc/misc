---
name: c9cu
description: 以编辑式索引组织个人研究、工程记录与自用工具
colors:
  archive-blue: "#075a9c"
  archive-blue-deep: "#034270"
  paper: "#f5f7fa"
  panel: "#ffffff"
  graphite: "#151b26"
  muted-graphite: "#5f6b7a"
  rule: "#d8dee7"
  status-amber: "#b98200"
  night-paper: "#151a23"
  night-panel: "#1b222d"
  night-ink: "#f3f6fa"
  night-muted: "#aeb8c5"
typography:
  display:
    fontFamily: "ui-serif, Iowan Old Style, Songti SC, STSong, Noto Serif CJK SC, Georgia, serif"
    fontSize: "clamp(3.15rem, 6.6vw, 5.9rem)"
    fontWeight: 700
    lineHeight: 0.98
    letterSpacing: "-0.04em"
  body:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, Noto Sans SC, PingFang SC, Microsoft YaHei, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.8
  label:
    fontFamily: "ui-sans-serif, -apple-system, BlinkMacSystemFont, Segoe UI, Noto Sans SC, PingFang SC, sans-serif"
    fontSize: "12px"
    fontWeight: 750
    lineHeight: 1.5
rounded:
  control: "9px"
  panel: "16px"
  compact: "5px"
spacing:
  xs: "8px"
  sm: "18px"
  md: "28px"
  lg: "48px"
components:
  consent-primary:
    backgroundColor: "{colors.archive-blue}"
    textColor: "{colors.panel}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "0 13px"
    height: "38px"
  archive-card:
    backgroundColor: "{colors.archive-blue}"
    textColor: "{colors.panel}"
    rounded: "{rounded.panel}"
    padding: "clamp(30px, 5vw, 60px)"
---

# Design System: c9cu

## Overview

**Creative North Star: "个人档案索引"**

c9cu 的界面像一份由本人持续整理的档案索引：先给身份和状态，再给证据与正文。视觉不模拟机构媒体，也不以促销组件制造权威感；冷色纸面、细规则线和开放列表承担主要秩序。

展示层使用编辑式衬线字形成个人出版物的气质，正文与导航保持清楚克制。深蓝只承担链接、主证据和关键动作，琥珀色只表示状态或边界。

**Key Characteristics:**

- 编辑式大标题与高可读正文并置。
- 依靠网格、留白和细规则线组织内容。
- 明暗主题共享同一语义色彩关系。
- 状态、来源和限制是视觉层级的一部分。

## Colors

配色是冷纸面上的石墨、档案蓝与少量状态琥珀；深色主题不是反相，而是保持相同的信息职责。

### Primary

- **档案蓝**：用于链接、字标重点、主要动作和首页代表作品；同一屏不大面积重复使用。
- **深档案蓝**：用于高强调文字链接与悬停状态。

### Secondary

- **状态琥珀**：仅用于历史状态、披露边界和类别提示，不用于普通装饰。

### Neutral

- **冷纸面与白色面板**：构成浅色主题的页面和局部承载层。
- **石墨与弱石墨**：分别承载主要文字和解释性文字。
- **规则线**：用于分节、列表和边界，不用阴影代替结构。
- **夜间纸面、面板、文字与弱文字**：在暗色主题中保持同样的层级关系。

**The Rare Accent Rule.** 档案蓝负责行动和证据，状态琥珀负责状态；两者不互相代替，也不把整页染成强调色。

## Typography

**Display Font:** 编辑式系统衬线组合，以 Iowan Old Style、宋体和 Georgia 作为实际可用回退。

**Body Font:** 系统无衬线组合，优先本机中文 UI 字体。

**Label/Mono Font:** 状态与导航沿用系统无衬线；编号使用系统等宽字体。

**Character:** 大标题带个人出版物的书卷感，正文保持工具界面的准确和效率。字号差异负责层级，不靠全大写眉题或装饰性徽章。

### Hierarchy

- **Display**（700，流体字号，0.98 行高）：首页、工具页、信任页和文章标题。
- **Headline**（700，19–40px）：分节标题与代表作品标题。
- **Title**（650–750，16–21px）：工具名、导航和局部标题。
- **Body**（400，16–18px，约 1.8 行高）：说明、文章和方法文字，主要阅读列控制在约 760px。
- **Label**（750，12–14px）：日期、状态、分类和辅助操作。

**The Two-Voice Rule.** 衬线只负责展示级标题；正文、导航、状态和交互全部使用无衬线。

## Layout

公共页面以 1180px 为最大宽度，两侧至少保留 20px；文章与信任页面收窄到 760px。首页首屏在桌面使用不对称双栏，左侧讲明身份，右侧用一项大型证据建立可信度；内容区使用开放列表而非同尺寸卡片墙。

900px 以下首页首屏变成单列，720px 以下主导航收进原生 `details` 菜单，640px 以下列表和元信息改为纵向。移动页面两侧保留 14px，所有数据表允许自身横向滚动，页面本身不产生横向溢出。

**The Open Index Rule.** 同类内容优先使用规则线分隔的开放列表；只有确实需要独立承载或浮层语义时才使用封闭面板。

## Elevation & Depth

系统默认扁平，以色块、边框和纸面层次表达深度。阴影只用于悬浮的同意面板、移动菜单和首页唯一的代表作品，不能成为普通列表的默认装饰。

### Shadow Vocabulary

- **悬浮面板**（柔和环境阴影）：用于必须高于正文的同意提示与移动菜单。
- **代表作品**（深蓝扩散阴影）：首页仅一处，用来标记主证据而不是制造一组悬浮卡片。

**The Flat-by-Default Rule.** 正文、列表、信任说明和状态提示保持平面；结构先靠规则线和留白完成。

## Shapes

页面主体与列表保持直角、开放边缘；独立工具工作区和浮层使用 9–16px 的温和圆角。状态提示使用完整边框加顶部状态线，避免单侧粗色条。图标只使用轮廓 SVG，并保持 20px 左右的视觉尺寸。

## Components

### Buttons

- **Shape:** 紧凑圆角控制（9px），最小高度 38px。
- **Primary:** 档案蓝底、白字，用于明确同意或主动作。
- **Hover / Focus:** 悬停保持颜色职责；键盘焦点统一使用高对比三像素轮廓。
- **Secondary:** 透明底配规则线边框，不能比主动作更醒目。

### Cards / Containers

- **Corner Style:** 普通内容不封卡；代表作品和浮层使用 16px 圆角。
- **Background:** 面板色承载工具工作区和浮层，代表作品使用档案蓝。
- **Shadow Strategy:** 遵守扁平优先原则。
- **Border:** 状态与工作区使用一像素规则线，历史状态可增加顶部琥珀线。
- **Internal Padding:** 浮层约 18px，工作区 20–34px，代表作品使用流体内边距。

### Navigation

桌面导航居中排列，14px 半粗字，默认弱石墨，悬停变为深档案蓝并加下划线。移动端使用原生 `details` 展开菜单；主题切换与菜单图标是等尺寸轮廓 SVG 控件。

### 代表作品面板

首页只允许一个大型深蓝证据面板。它同时承载分类、日期、标题、摘要与阅读入口；标题比例明显高于摘要，装饰几何不能干扰文本。

### 状态与披露

研究边界使用开放式上下规则线；已归档研究使用完整边框和顶部琥珀状态线。状态文字必须直说“历史”“停止刷新”或具体限制，不能只靠颜色表达。

## Do's and Don'ts

### Do:

- **Do** 先展示作者、日期、状态、来源或处理位置，再要求访客相信结果。
- **Do** 用规则线、留白和文字层级组织跨主题内容。
- **Do** 让移动端从多栏自然重排为单列，并保持页面无横向溢出。
- **Do** 在明暗主题中保持档案蓝、状态琥珀和中性色的语义一致。

### Don't:

- **Don't** 使用装饰性眉题、全大写口号或无信息量徽章填充标题上方。
- **Don't** 把每项内容包装成同尺寸圆角卡片。
- **Don't** 用单侧粗色条、发光阴影、渐变文字或表情符号代替层级。
- **Don't** 编造头像、资历、统计数字或机构背书来制造可信度。
