# Citation earliest 版本的同年歧義

## 原 annotation

> 這個優先度較後，先合併 branch 後我再來弄。

## 問題

當 `version_kind="earliest"` 找到多個候選，而候選只有年份、沒有足以判斷先後的完整日期時，目前 resolver 仍會依 score、rank 與 provider 排序後選出一筆。

例如 preprint 與 published version 都標示 2020 年，但沒有月份或關係證據；系統可能選擇 rank 較前的 published version，卻無法證明它真的是最早版本。

## 判定

- 優先度：後。
- 狀態：不阻擋 branch 整併，整併完成後再處理。
- 影響：可能保存錯誤 manifestation，但只影響要求 `earliest` 且候選時間證據不足的情境。

## 後續方向

- 若最早候選能由完整日期或明確版本關係唯一判斷，才回傳 eligible。
- 同年、缺日期或證據相同時，回傳 ambiguity，而不是用 provider rank 代替時間證據。
- 可考慮納入 online date、print date、repository deposited date 與 relation metadata。

## 驗收條件

- 不同年份候選仍能選出較早版本。
- 同年且無完整日期的不同 DOI 候選必須回傳 ambiguity。
- 缺年份的多候選不得靜默選擇。
- 有可靠完整日期或明確版本關係時可以確定選擇。
