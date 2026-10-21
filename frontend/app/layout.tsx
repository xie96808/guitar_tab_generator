import "./globals.css";

export const metadata = {
  title: "Guitar Tab Generator (MVP)"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="container">{children}</div>
      </body>
    </html>
  );
}

