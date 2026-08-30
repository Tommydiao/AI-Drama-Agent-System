import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = { title: "AI 短剧 Agent · Mock MVP", description: "生成可播放的竖屏短剧样片" };

export default function Layout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}

