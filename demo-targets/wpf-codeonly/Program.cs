using System;
using System.IO;
using System.Reflection;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Markup;
using System.Windows.Media;

namespace WpfDemo
{
    /// <summary>
    /// 纯代码（无 XAML 编译器）WPF 演示靶场。
    /// 控件颜色一律走 DynamicResource 键：AppBg / AppFg / Accent。
    /// 启动时若同目录存在 theme.xaml，则外挂加载为 ResourceDictionary，
    /// 覆盖内置浅色资源；不存在则使用内置浅色兜底。
    /// </summary>
    class Program
    {
        [STAThread]
        static void Main()
        {
            var app = new Application();
            app.Resources = new ResourceDictionary();

            // 1) 内置浅色兜底资源（先加入 MergedDictionaries）
            app.Resources.MergedDictionaries.Add(BuildBuiltinLight());

            // 2) 外挂 theme.xaml（后加入者在合并字典查找中优先生效）
            string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string themePath = Path.Combine(dir, "theme.xaml");
            if (File.Exists(themePath))
            {
                try
                {
                    string xaml = File.ReadAllText(themePath);
                    var ext = (ResourceDictionary)XamlReader.Parse(xaml);
                    app.Resources.MergedDictionaries.Add(ext);
                }
                catch (Exception ex)
                {
                    Console.WriteLine("theme.xaml load failed, fallback to builtin: " + ex.Message);
                }
            }

            var win = new Window();
            win.Title = "Reskinner WPF Demo";
            win.Width = 640;
            win.Height = 420;
            win.SetResourceReference(Window.BackgroundProperty, "AppBg");
            win.SetResourceReference(Window.ForegroundProperty, "AppFg");

            var panel = new StackPanel { Margin = new Thickness(12) };

            var list = new ListBox { Height = 120 };
            list.Items.Add("Alpha");
            list.Items.Add("Beta");
            list.Items.Add("Gamma");
            list.Items.Add("Delta");
            list.SetResourceReference(Control.BackgroundProperty, "AppBg");
            list.SetResourceReference(Control.ForegroundProperty, "AppFg");
            panel.Children.Add(list);

            var box = new TextBox { Height = 80, Text = "text area ..." };
            box.SetResourceReference(Control.BackgroundProperty, "AppBg");
            box.SetResourceReference(Control.ForegroundProperty, "AppFg");
            panel.Children.Add(box);

            var status = new StatusBar();
            var statusItem = new StatusBarItem { Content = "status bar" };
            status.Items.Add(statusItem);
            status.SetResourceReference(Control.BackgroundProperty, "Accent");
            status.SetResourceReference(Control.ForegroundProperty, "AppFg");
            panel.Children.Add(status);

            var btn = new Button { Content = "Click Me", Padding = new Thickness(16, 6, 16, 6) };
            btn.SetResourceReference(Control.BackgroundProperty, "Accent");
            btn.SetResourceReference(Control.ForegroundProperty, "AppFg");
            btn.Click += (s, e) => { statusItem.Content = "clicked"; };
            panel.Children.Add(btn);

            win.Content = panel;

            app.Run(win);
        }

        static ResourceDictionary BuildBuiltinLight()
        {
            var d = new ResourceDictionary();
            d["AppBg"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#F5F5F0"));
            d["AppFg"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#1A1A1A"));
            d["Accent"] = new SolidColorBrush((Color)ColorConverter.ConvertFromString("#B9D4F0"));
            return d;
        }
    }
}
