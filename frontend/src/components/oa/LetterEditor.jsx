// ویرایشگر متن نامه (TipTap) — فقط امکاناتی که پاک‌ساز سرور (core/oa_html.py) نگه می‌دارد:
// پاراگراف، تیتر ۲ و ۳، پررنگ/کج/زیرخط/خط‌خورده، فهرست، نقل‌قول، تراز متن و جدول. خروجی HTML با onChange.
import { useEffect } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import Table from "@tiptap/extension-table";
import TableRow from "@tiptap/extension-table-row";
import TableHeader from "@tiptap/extension-table-header";
import TableCell from "@tiptap/extension-table-cell";
import { Box, Divider, IconButton, Stack, Tooltip } from "@mui/material";
import FormatBoldIcon from "@mui/icons-material/FormatBold";
import FormatItalicIcon from "@mui/icons-material/FormatItalic";
import FormatUnderlinedIcon from "@mui/icons-material/FormatUnderlined";
import StrikethroughSIcon from "@mui/icons-material/StrikethroughS";
import FormatListBulletedIcon from "@mui/icons-material/FormatListBulleted";
import FormatListNumberedIcon from "@mui/icons-material/FormatListNumbered";
import FormatQuoteIcon from "@mui/icons-material/FormatQuote";
import FormatAlignRightIcon from "@mui/icons-material/FormatAlignRight";
import FormatAlignCenterIcon from "@mui/icons-material/FormatAlignCenter";
import FormatAlignLeftIcon from "@mui/icons-material/FormatAlignLeft";
import FormatAlignJustifyIcon from "@mui/icons-material/FormatAlignJustify";
import TitleIcon from "@mui/icons-material/Title";
import TextFieldsIcon from "@mui/icons-material/TextFields";
import TableChartOutlinedIcon from "@mui/icons-material/TableChartOutlined";
import PlaylistAddIcon from "@mui/icons-material/PlaylistAdd";
import ViewWeekOutlinedIcon from "@mui/icons-material/ViewWeekOutlined";
import DeleteSweepOutlinedIcon from "@mui/icons-material/DeleteSweepOutlined";
import UndoIcon from "@mui/icons-material/Undo";
import RedoIcon from "@mui/icons-material/Redo";

function Btn({ title, icon, onClick, active, disabled }) {
  return (
    <Tooltip title={title}>
      <span>
        <IconButton
          size="small"
          onClick={onClick}
          disabled={disabled}
          color={active ? "primary" : "default"}
          sx={{ borderRadius: 1, bgcolor: active ? "action.selected" : "transparent" }}
        >
          {icon}
        </IconButton>
      </span>
    </Tooltip>
  );
}

export default function LetterEditor({ value, onChange, disabled = false }) {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [2, 3] }, code: false, codeBlock: false, horizontalRule: false }),
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"], alignments: ["right", "center", "left", "justify"] }),
      Table.configure({ resizable: false }),
      TableRow,
      TableHeader,
      TableCell,
    ],
    content: value || "",
    editable: !disabled,
    editorProps: { attributes: { dir: "rtl", class: "oa-editor" } },
    onUpdate: ({ editor: ed }) => onChange?.(ed.isEmpty ? "" : ed.getHTML()),
  });

  // متن بیرونی (مثلاً بعد از بارگذاری پیش‌نویس) فقط وقتی با متن ویرایشگر فرق دارد جایگزین می‌شود
  useEffect(() => {
    if (!editor) return;
    const current = editor.isEmpty ? "" : editor.getHTML();
    if ((value || "") !== current) editor.commands.setContent(value || "", false);
  }, [editor, value]);

  useEffect(() => {
    editor?.setEditable(!disabled);
  }, [editor, disabled]);

  if (!editor) return null;
  const c = () => editor.chain().focus();
  const inTable = editor.isActive("table");

  return (
    <Box sx={{ border: 1, borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
      <Stack direction="row" flexWrap="wrap" alignItems="center" sx={{ p: 0.5, gap: 0.25, bgcolor: "action.hover" }}>
        <Btn title="پاراگراف" icon={<TextFieldsIcon fontSize="small" />} onClick={() => c().setParagraph().run()} active={editor.isActive("paragraph")} />
        <Btn title="تیتر" icon={<TitleIcon fontSize="small" />} onClick={() => c().toggleHeading({ level: 2 }).run()} active={editor.isActive("heading", { level: 2 })} />
        <Btn title="تیتر کوچک" icon={<TitleIcon sx={{ fontSize: 15 }} />} onClick={() => c().toggleHeading({ level: 3 }).run()} active={editor.isActive("heading", { level: 3 })} />
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Btn title="پررنگ" icon={<FormatBoldIcon fontSize="small" />} onClick={() => c().toggleBold().run()} active={editor.isActive("bold")} />
        <Btn title="کج" icon={<FormatItalicIcon fontSize="small" />} onClick={() => c().toggleItalic().run()} active={editor.isActive("italic")} />
        <Btn title="زیرخط" icon={<FormatUnderlinedIcon fontSize="small" />} onClick={() => c().toggleUnderline().run()} active={editor.isActive("underline")} />
        <Btn title="خط‌خورده" icon={<StrikethroughSIcon fontSize="small" />} onClick={() => c().toggleStrike().run()} active={editor.isActive("strike")} />
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Btn title="فهرست نقطه‌ای" icon={<FormatListBulletedIcon fontSize="small" />} onClick={() => c().toggleBulletList().run()} active={editor.isActive("bulletList")} />
        <Btn title="فهرست شماره‌دار" icon={<FormatListNumberedIcon fontSize="small" />} onClick={() => c().toggleOrderedList().run()} active={editor.isActive("orderedList")} />
        <Btn title="نقل‌قول" icon={<FormatQuoteIcon fontSize="small" />} onClick={() => c().toggleBlockquote().run()} active={editor.isActive("blockquote")} />
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Btn title="راست‌چین" icon={<FormatAlignRightIcon fontSize="small" />} onClick={() => c().setTextAlign("right").run()} active={editor.isActive({ textAlign: "right" })} />
        <Btn title="وسط‌چین" icon={<FormatAlignCenterIcon fontSize="small" />} onClick={() => c().setTextAlign("center").run()} active={editor.isActive({ textAlign: "center" })} />
        <Btn title="چپ‌چین" icon={<FormatAlignLeftIcon fontSize="small" />} onClick={() => c().setTextAlign("left").run()} active={editor.isActive({ textAlign: "left" })} />
        <Btn title="تراز دوطرفه" icon={<FormatAlignJustifyIcon fontSize="small" />} onClick={() => c().setTextAlign("justify").run()} active={editor.isActive({ textAlign: "justify" })} />
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Btn title="درج جدول ۳×۳" icon={<TableChartOutlinedIcon fontSize="small" />} onClick={() => c().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()} disabled={inTable} />
        <Btn title="افزودن ردیف" icon={<PlaylistAddIcon fontSize="small" />} onClick={() => c().addRowAfter().run()} disabled={!inTable} />
        <Btn title="افزودن ستون" icon={<ViewWeekOutlinedIcon fontSize="small" />} onClick={() => c().addColumnAfter().run()} disabled={!inTable} />
        <Btn title="حذف جدول" icon={<DeleteSweepOutlinedIcon fontSize="small" />} onClick={() => c().deleteTable().run()} disabled={!inTable} />
        <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />
        <Btn title="برگشت" icon={<UndoIcon fontSize="small" />} onClick={() => c().undo().run()} disabled={!editor.can().undo()} />
        <Btn title="تکرار" icon={<RedoIcon fontSize="small" />} onClick={() => c().redo().run()} disabled={!editor.can().redo()} />
      </Stack>
      <Box
        sx={{
          p: 2,
          minHeight: 320,
          "& .oa-editor": { outline: "none", minHeight: 300, lineHeight: 1.9, fontSize: 15 },
          "& .oa-editor p": { my: 0.75 },
          "& .oa-editor table": { borderCollapse: "collapse", width: "100%", my: 1 },
          "& .oa-editor td, & .oa-editor th": { border: 1, borderColor: "grey.500", p: 0.75, verticalAlign: "top", minWidth: 40 },
          "& .oa-editor th": { bgcolor: "action.hover" },
          "& .oa-editor .selectedCell": { bgcolor: "action.selected" },
          "& .oa-editor blockquote": { borderInlineStart: 4, borderColor: "divider", m: 0, pr: 1.5, color: "text.secondary" },
          "& .oa-editor ul, & .oa-editor ol": { pr: 3, pl: 0 },
        }}
      >
        <EditorContent editor={editor} />
      </Box>
    </Box>
  );
}
