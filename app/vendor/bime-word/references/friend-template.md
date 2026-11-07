# 朋友範本的證據

來源：使用者朋友手做的 Word 範本 `論文格式.docx`，SHA-256 `6ab7ee5aa6198e4698708904001db68ad9575124392c3a8606eac31540f0e880`，2026-09-30 讀取。檔案不打包進本 skill（它是朋友的作品，內含範例圖片），這裡只記錄採用或拒絕的參數，以及它們在 XML 裡的位置。

範本是一份空白論文骨架：誌謝、中文摘要、英文摘要、目錄、圖目錄、表目錄、符號說明，然後第一章到第七章（最後兩章是參考文獻與附錄），內含兩張示範圖與一個示範表。沒有封面、標題頁與審定書。

## 採用的參數

| 參數 | XML 證據 |
|---|---|
| 字型與字級 | `styles.xml` docDefaults：`rFonts ascii/hAnsi="Times New Roman" eastAsia="標楷體"`、`sz=24` |
| 行距 1.5、段後 0、首行縮排兩字 | Normal（styleId `a1`）：`spacing after=0 line=360 lineRule=auto`、`ind firstLineChars=200` |
| 文件格線 | 兩個 `sectPr` 都是 `docGrid type="lines" linePitch="360"` |
| 邊界 | 兩個 `sectPr` 都是 `pgMar top=1701 right=1701 bottom=1134 left=1701`（3／3／2／3 cm），前置頁分節也一樣 |
| 頁首距離 | `pgMar header=851`（1.5 cm） |
| 頁碼 | 第一分節 `pgNumType fmt=lowerRoman`（從誌謝起算 i），第二分節 `pgNumType start=1`（阿拉伯數字）；`footer2.xml` 的 PAGE 欄位段落 `jc=center`，footer 樣式 `sz=20`（10 pt） |
| 章標題 | heading 1：`b`、`sz=36`、`jc=center`、`spacing before=240 after=120`、`keepNext keepLines` |
| 節標題 | heading 2、heading 3：`b`、`sz=28` |
| 前置頁標題 | Title（`a5`）：`b`、`sz=36`、`jc=center`，不在大綱層級內 |
| 章節編號 | `numbering.xml` abstractNum 1：`lvlText="第%1章"`（taiwaneseCountingThousand）、`"%1.%2"`、`"%1.%2.%3"`（isLgl） |
| 圖表編號 | 同一清單第 4、5 層：`lvlText="圖%1-%4"`、`"表%1-%5"`，`lvlRestart=1`（只在新章重新起算）、`isLgl`，沒有 `suff`（編號後接定位字元） |
| 圖表標題樣式 | 「圖內容」（`a`）：`jc=center`、`keepNext`、無粗體；「表內容」（`a0`）以圖內容為基礎 |
| 圖片段落 | 「圖片位置」（`af6`）：`jc=center`、`keepNext` |
| 表格 | 示範表套 Table Grid（`af8`）：六邊 `single sz=4`；自訂「表格」樣式（`af7`）：同樣框線、`jc=center` |
| 目錄 | `TOC \h \z \t "標題 1,2,標題 2,3,標題 3,4,標題,1"`：前置頁標題、章、節、小節四層；toc 樣式右對齊點線定位點 `pos=8494` |
| 圖目錄、表目錄 | `TOC \h \z \t "圖內容,1"`、`TOC \h \z \t "表內容,1"` |
| 前置頁順序 | 誌謝、中文摘要、英文摘要、目錄、圖目錄、表目錄、符號說明，各自一頁 |

## 拒絕的參數（系辦優先）

| 參數 | XML 證據 | 原因 |
|---|---|---|
| 頁尾高度 | `pgMar footer=992`（1.75 cm）；`footer2.xml` 在頁碼段落後還有一個空段落，兩段都是 10 pt、1.5 倍行距 | 頁尾頂端約 2.97 cm，Word 會把本文下緣推到約 3 cm，違反二.5 的下 2 cm |
| 頁碼縮排 | 頁碼段落 `ind firstLine=400` | 置中後偏右約 0.35 cm |
| 後置部分編章號 | 參考文獻、附錄用 heading 1，被清單編成「第六章」「第七章」 | 系辦目錄範例不編章號 |
| 目錄收錄自己 | 目錄快取項目「目錄 iv」 | 系辦目錄範例沒有 |
| 直接格式行距 | 誌謝、兩個摘要與若干空段落：`spacing after=160 line=278`（1.16 倍） | 與範本自己的 1.5 倍不一致 |
| heading 4 顏色 | `color val=0F4761 themeColor=accent1` | 三.2 黑色 |
| 空白標題段落 | 第三章末尾放分頁符號的段落套 heading 3 | 會印出孤立的「3.1.3」 |

## 沒有採用、但也不是錯的做法

範本以多層次清單產生章號與圖表號，好處是插入新節或新圖後 Word 會自動重編。轉檔輸出改用文字編號，讓 Pandoc 產生的內容在任何 Word 都顯示一致；稽核會把清單編號還原成實際顯示的文字再檢查，局部新增也會沿用收件文件的編號樣式並核對編號。
