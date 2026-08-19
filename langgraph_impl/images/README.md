# UI 截图目录

把文案所在界面的截图放这里，然后在提交单里用 `"ui_shot": "images/文件名.png"` 引用。

- 有图时：图片会作为多模态输入发给 en-copywriter、multilingual-localizer、visual-context-checker，
  让模型结合界面语境翻译/走查。
- 没图 / 路径找不到：自动跳过，按纯文本正常跑（不报错）。
- 仅真实模型模式生效；桩模式不看图。
- 支持 png/jpg/webp（需所用模型支持视觉输入；gpt-5.5 等多模态模型可用）。
