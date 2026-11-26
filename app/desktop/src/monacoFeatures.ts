// Monaco editor contributions for the document editor. `editor.api` registers
// none of them, so without these imports there is no find widget, right-click
// menu, hover, folding, bracket matching, comment toggle or line/word commands.
// Each entry is a side-effect module that Monaco ships with its own `.d.ts`;
// Vite bundles them into the lazily loaded editor chunk (no CDN).
//
// `contextmenu` replaces the native WebView menu, so `clipboard` must stay with
// it or right-click loses Cut/Copy/Paste. `codicon` supplies the icon font the
// find widget, menus and folding chevrons draw with. The suggest list is not
// here: Monaco has no typed entry for `suggestController` (plan phase D1A).
import "monaco-editor/features/codicon/register";
import "monaco-editor/features/contextmenu/register";
import "monaco-editor/features/clipboard/register";
import "monaco-editor/features/find/register";
import "monaco-editor/features/bracketMatching/register";
import "monaco-editor/features/comment/register";
import "monaco-editor/features/linesOperations/register";
import "monaco-editor/features/multicursor/register";
import "monaco-editor/features/wordOperations/register";
import "monaco-editor/features/cursorUndo/register";
import "monaco-editor/features/smartSelect/register";
import "monaco-editor/features/indentation/register";
import "monaco-editor/features/hover/register";
import "monaco-editor/features/folding/register";
import "monaco-editor/features/wordHighlighter/register";
