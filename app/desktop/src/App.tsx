import { getTauriVersion } from "@tauri-apps/api/app";
import { useEffect, useState } from "react";

const navigationItems = ["對話", "知識庫", "擴充功能", "診斷"];

function platformLabel(): string {
  return navigator.userAgent.includes("Linux") ? "Linux" : navigator.platform;
}

export default function App() {
  const [tauriVersion, setTauriVersion] = useState("讀取中…");

  useEffect(() => {
    let active = true;

    void getTauriVersion()
      .then((version) => {
        if (active) {
          setTauriVersion(version);
        }
      })
      .catch(() => {
        if (active) {
          setTauriVersion("僅瀏覽器預覽");
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">LOCAL RESEARCH WORKSPACE</p>
          <h1>Research Agent</h1>
        </div>
        <div className="shell-status" role="status" aria-live="polite">
          <span className="status-dot" aria-hidden="true" />
          Desktop shell ready
        </div>
      </header>

      <div className="workspace">
        <nav className="navigation" aria-label="主要功能">
          <p className="navigation-label">功能</p>
          {navigationItems.map((item) => (
            <button key={item} type="button" disabled>
              <span>{item}</span>
              <span aria-hidden="true">即將推出</span>
            </button>
          ))}
        </nav>

        <main className="content">
          <section className="ready-card" aria-labelledby="ready-title">
            <div className="ready-mark" aria-hidden="true">✓</div>
            <div>
              <p className="section-kicker">第 03 步</p>
              <h2 id="ready-title">桌面外殼已就緒</h2>
              <p>
                Tauri、React 與 WebKitGTK 已在 Linux 環境中連線。這個階段尚未啟動
                Python backend，也不會讀寫研究資料。
              </p>
            </div>
          </section>

          <section className="runtime-card" aria-labelledby="runtime-title">
            <div>
              <p className="section-kicker">執行環境</p>
              <h2 id="runtime-title">本機桌面資訊</h2>
            </div>
            <dl>
              <div>
                <dt>平台</dt>
                <dd>{platformLabel()}</dd>
              </div>
              <div>
                <dt>Tauri</dt>
                <dd>{tauriVersion}</dd>
              </div>
              <div>
                <dt>目前能力</dt>
                <dd>僅桌面外殼</dd>
              </div>
            </dl>
          </section>
        </main>
      </div>

      <footer>
        <span>Current session only</span>
        <span>尚未連接 Python backend</span>
      </footer>
    </div>
  );
}
