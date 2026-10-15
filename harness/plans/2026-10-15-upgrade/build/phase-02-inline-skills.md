# P2｜行內多 Skill 真正作用於文件

來源與目標：[GOALS.md](../GOALS.md)。共同設計、批准／成本與失敗處理：[PLANS.md](../PLANS.md)。執行狀態、證據與下一步：[build-log.md](../build-log.md)。本檔只維護階段定義；驗證命令參考 [PLANS.md 第 5 節](../PLANS.md#5-驗證命令與成本界線)。

**依賴：** P1；引用契約批准。**涵蓋：** G2、G6 的學術寫作流程。

沿用可用 Skill catalog，將目前 slash 自動完成擴為游標所在的 @ token。保留 slash 行為，候選選取只替換當前 token，不截掉前後文字。Session 依[PLANS.md 第 3.2 節](../PLANS.md#32-skill摘要與權限)使用全部引用的指引與工具，在成功、失敗、拒絕及 retry 路徑清理一次性狀態；不把 Skill 指令殘留到下一回合。

**必需驗收：**

- 在句首／中／尾及游標回移位置輸入部分名稱；方向鍵、Enter 選取、Esc、滑鼠可用，選單開啟時 Enter 不誤送出。
- 中文輸入法組字、Shift+Enter、普通 email 與不存在的 Skill 均有可預期行為；修改草稿後引用位置不過期。
- 選段後 `使用 @academic-paper-writing 潤飾這段` 收到正確版本／範圍，完成一次指定範圍修改並存檔。
- 使用兩個實際 catalog Skill；在離線模型輸入確認兩份指引可見，明確「先…再…」的第二步取得前一步產物；包含 citation 時仍保留引用核驗與清理。
- 模擬某 Skill 缺工具與真正指引矛盾：顯示原因／提問，不靜默漏載；下一回合不殘留技能或臨時 Normal 模式。
- 兩個 Skill 都有同名 references 檔案時，依各自 Skill root 讀取正確檔案；同時核對 session、AgentState、graph、policy_node 的有效工具集合一致。citation／skill-installer 的 session authority、pending action、清理與模式還原沿用真實本回合授權，不能互相清掉必要狀態或把文件內容當授權。

**交付：** 多引用、prompt 關係、文件上下文走通同一回合；不存在新排程框架。
