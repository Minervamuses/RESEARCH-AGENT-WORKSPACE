"""Schema child order for the WordprocessingML elements this package creates or edits.

Microsoft Word validates the order of child elements; LibreOffice does not. Every
element the package adds goes through `insert_ordered`, and outputs are checked with
`order_errors` before they are committed.
Order tables follow ECMA-376 Part 1 (transitional) sequences for CT_PPr, CT_RPr,
CT_ParaRPr, CT_R, CT_SectPr, CT_Settings and CT_Style.
"""
from __future__ import annotations

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

PPR = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr', 'widowControl', 'numPr',
       'suppressLineNumbers', 'pBdr', 'shd', 'tabs', 'suppressAutoHyphens', 'kinsoku', 'wordWrap',
       'overflowPunct', 'topLinePunct', 'autoSpaceDE', 'autoSpaceDN', 'bidi', 'adjustRightInd',
       'snapToGrid', 'spacing', 'ind', 'contextualSpacing', 'mirrorIndents', 'suppressOverlap', 'jc',
       'textDirection', 'textAlignment', 'textboxTightWrap', 'outlineLvl', 'divId', 'cnfStyle',
       'rPr', 'sectPr', 'pPrChange']
RPR = ['ins', 'del', 'moveFrom', 'moveTo',
       'rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike', 'outline',
       'shadow', 'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish', 'webHidden', 'color', 'spacing',
       'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u', 'effect', 'bdr', 'shd', 'fitText',
       'vertAlign', 'rtl', 'cs', 'em', 'lang', 'eastAsianLayout', 'specVanish', 'oMath', 'rPrChange']
SECTPR = ['headerReference', 'footerReference', 'footnotePr', 'endnotePr', 'type', 'pgSz', 'pgMar',
          'paperSrc', 'pgBorders', 'lnNumType', 'pgNumType', 'cols', 'formProt', 'vAlign', 'noEndnote',
          'titlePg', 'textDirection', 'bidi', 'rtlGutter', 'docGrid', 'printerSettings', 'sectPrChange']
SETTINGS = ['writeProtection', 'view', 'zoom', 'removePersonalInformation', 'removeDateAndTime',
            'doNotDisplayPageBoundaries', 'displayBackgroundShape', 'printPostScriptOverText',
            'printFractionalCharacterWidth', 'printFormsData', 'embedTrueTypeFonts', 'embedSystemFonts',
            'saveSubsetFonts', 'saveFormsData', 'mirrorMargins', 'alignBordersAndEdges',
            'bordersDoNotSurroundHeader', 'bordersDoNotSurroundFooter', 'gutterAtTop',
            'hideSpellingErrors', 'hideGrammaticalErrors', 'activeWritingStyle', 'proofState',
            'formsDesign', 'attachedTemplate', 'linkStyles', 'stylePaneFormatFilter',
            'stylePaneSortMethod', 'documentType', 'mailMerge', 'revisionView', 'trackRevisions',
            'doNotTrackMoves', 'doNotTrackFormatting', 'documentProtection', 'autoFormatOverride',
            'styleLockTheme', 'styleLockQFSet', 'defaultTabStop', 'autoHyphenation',
            'consecutiveHyphenLimit', 'hyphenationZone', 'doNotHyphenateCaps', 'showEnvelope',
            'summaryLength', 'clickAndTypeStyle', 'defaultTableStyle', 'evenAndOddHeaders',
            'bookFoldRevPrinting', 'bookFoldPrinting', 'bookFoldPrintingSheets',
            'drawingGridHorizontalSpacing', 'drawingGridVerticalSpacing',
            'displayHorizontalDrawingGridEvery', 'displayVerticalDrawingGridEvery',
            'doNotUseMarginsForDrawingGridOrigin', 'drawingGridHorizontalOrigin',
            'drawingGridVerticalOrigin', 'doNotShadeFormData', 'noPunctuationKerning',
            'characterSpacingControl', 'printTwoOnOne', 'strictFirstAndLastChars', 'noLineBreaksAfter',
            'noLineBreaksBefore', 'savePreviewPicture', 'doNotValidateAgainstSchema', 'saveInvalidXml',
            'ignoreMixedContent', 'alwaysShowPlaceholderText', 'doNotDemarcateInvalidXml',
            'saveXmlDataOnly', 'useXSLTWhenSaving', 'saveThroughXslt', 'showXMLTags',
            'alwaysMergeEmptyNamespace', 'updateFields', 'hdrShapeDefaults', 'footnotePr', 'endnotePr',
            'compat', 'docVars', 'rsids', 'mathPr', 'attachedSchema', 'themeFontLang',
            'clrSchemeMapping', 'doNotIncludeSubdocsInStats', 'doNotAutoCompressPictures',
            'forceUpgrade', 'captions', 'readModeInkLockDown', 'smartTagType', 'schemaLibrary',
            'shapeDefaults', 'doNotEmbedSmartTags', 'decimalSymbol', 'listSeparator']
STYLE = ['name', 'aliases', 'basedOn', 'next', 'link', 'autoRedefine', 'hidden', 'uiPriority',
         'semiHidden', 'unhideWhenUsed', 'qFormat', 'locked', 'personal', 'personalCompose',
         'personalReply', 'rsid', 'pPr', 'rPr', 'tblPr', 'trPr', 'tcPr', 'tblStylePr']
TBLPR = ['tblStyle', 'tblpPr', 'tblOverlap', 'bidiVisual', 'tblStyleRowBandSize', 'tblStyleColBandSize', 'tblW', 'jc',
         'tblCellSpacing', 'tblInd', 'tblBorders', 'shd', 'tblLayout', 'tblCellMar', 'tblLook', 'tblCaption',
         'tblDescription', 'tblPrChange']
# In a run or paragraph only the property element's position is constrained: it comes first.
FIRST = {'r': 'rPr', 'p': 'pPr'}

TABLES = {'pPr': PPR, 'rPr': RPR, 'sectPr': SECTPR, 'settings': SETTINGS, 'style': STYLE, 'r': ['rPr'], 'p': ['pPr'], 'tblPr': TBLPR}


def _local(tag) -> str | None:
    if not isinstance(tag, str) or not tag.startswith('{' + W + '}'):
        return None
    return tag.split('}', 1)[1]


def _rank(parent_local: str, child_tag) -> int | None:
    table = TABLES.get(parent_local)
    local = _local(child_tag)
    if table is None or local is None:
        return None
    if parent_local in FIRST:
        return 0 if local == FIRST[parent_local] else 1
    return table.index(local) if local in table else None


def insert_ordered(parent, node):
    """Insert node into parent at the schema position; unknown elements keep their place."""
    parent_local = _local(parent.tag)
    rank = _rank(parent_local, node.tag) if parent_local else None
    if rank is None:
        parent.append(node)
        return node
    for index, existing in enumerate(parent):
        other = _rank(parent_local, existing.tag)
        if other is not None and other > rank:
            parent.insert(index, node)
            return node
    # Extension elements (w14/w15, mc:AlternateContent) stay last in settings.
    if parent_local == 'settings':
        for index, existing in enumerate(parent):
            if _local(existing.tag) is None:
                parent.insert(index, node)
                return node
    parent.append(node)
    return node


def order_errors(root, part='document'):
    """Return (part, path, message) tuples for out-of-order children the package manages."""
    errors = []
    for node in root.iter():
        parent_local = _local(node.tag)
        if parent_local not in TABLES:
            continue
        last = -1
        last_name = None
        for c in node:
            rank = _rank(parent_local, c.tag)
            if rank is None:
                continue
            if rank < last:
                errors.append((part, parent_local, f'<w:{_local(c.tag)}> appears after <w:{last_name}> inside <w:{parent_local}>'))
                break
            last, last_name = rank, _local(c.tag)
    return errors
