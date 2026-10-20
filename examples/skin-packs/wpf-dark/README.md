# wpf-dark 换肤包

WPF 靶场的深蓝暗色外挂 ResourceDictionary 换肤包。

## 适用路径（合法且唯一）

`demo-targets/wpf-codeonly` 在启动时通过 `XamlReader.Parse` 加载同目录 `theme.xaml`，
控件颜色走 DynamicResource 键 `AppBg` / `AppFg` / `Accent`。本包只做一件事：
`replace_file` 把 `theme.xaml` 换成暗色版。

## 合规边界（必须如实声明）

- 真实成品 WPF 应用的样式编译为 **BAML**，内嵌在程序集资源中，**没有官方回编工具链**。
- 本工具箱对 BAML 内嵌资源保持**只读 / `unsupported`**：不做 IL 改写、不反编译重编译、不破坏强命名 / 签名。
- 本换肤包是研究案例库中明确记载的「外挂松散 ResourceDictionary」合法替代路径，
  仅用于演示静态资源替换主路径，不代表可以对任意闭源 WPF 软件做同样操作。
