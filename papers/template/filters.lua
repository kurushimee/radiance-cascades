-- The Markdown links PNG figures so that it renders on GitHub; the paper takes the vector PDF beside each.
function Image(img)
  local pdf = img.src:gsub("%.png$", ".pdf")
  if pdf ~= img.src and io.open(pdf, "r") then
    img.src = pdf
  end
  return img
end

local appendix_started = false

-- A heading with the class "appendix" starts the appendices. Floats of the body are set before it, and the appendix's
-- own floats stay where they stand, so none rises above its heading; pages there end ragged rather than spread out
-- around them.
function Header(h)
  if appendix_started or not h.classes:includes("appendix") then
    return h
  end
  appendix_started = true
  local start = "\\FloatBarrier\\raggedbottom\\floatplacement{figure}{H}\\floatplacement{table}{H}\\appendix"
  return {pandoc.RawBlock("latex", start), h}
end

local latex_special = {
  ["\\"] = "\\textbackslash{}", ["~"] = "\\textasciitilde{}", ["^"] = "\\textasciicircum{}",
  ["%"] = "\\%", ["&"] = "\\&", ["#"] = "\\#", ["_"] = "\\_", ["{"] = "\\{", ["}"] = "\\}", ["$"] = "\\$",
}

local function latex_escape(text)
  return (text:gsub("[\\%%&#_{}%$%^~]", latex_special))
end

-- acmart asks every figure for a text description; the caption serves. It joins the image's own block, since a second
-- block would turn the figure into two side-by-side subfigures.
function Figure(fig)
  local text = latex_escape(pandoc.utils.stringify(fig.caption.long))
  table.insert(fig.content[1].content, pandoc.RawInline("latex", "\\Description{" .. text .. "}"))
  return fig
end

local function latex(blocks)
  return (pandoc.write(pandoc.Pandoc(blocks), "latex"):gsub("%s+$", ""):gsub("\n", " "))
end

local function row_latex(row)
  local cells = {}
  for _, cell in ipairs(row.cells) do
    table.insert(cells, latex(cell.contents))
  end
  return table.concat(cells, " & ") .. " \\\\"
end

-- longtable misjudges the room left on a page that also holds floats and runs off its bottom, so each table is a
-- float of its own; every table in these papers fits on one page.
function Table(tbl)
  local count = #tbl.colspecs
  local columns = {}
  for _, spec in ipairs(tbl.colspecs) do
    local width = spec[2]
    if type(width) == "number" then
      table.insert(columns, string.format(
        ">{\\raggedright\\arraybackslash}p{(\\linewidth - %d\\tabcolsep) * \\real{%.4f}}", 2 * (count - 1), width))
    else
      table.insert(columns, "l")
    end
  end
  local lines = {"\\begin{table}"}
  local caption = pandoc.utils.blocks_to_inlines(tbl.caption.long)
  if #caption > 0 then
    local label = tbl.identifier ~= "" and ("\\label{" .. tbl.identifier .. "}") or ""
    table.insert(lines, "\\caption{" .. latex({pandoc.Plain(caption)}) .. "}" .. label)
  end
  table.insert(lines, "\\begin{tabular}{@{}" .. table.concat(columns) .. "@{}}")
  table.insert(lines, "\\toprule")
  for _, row in ipairs(tbl.head.rows) do
    table.insert(lines, row_latex(row))
  end
  table.insert(lines, "\\midrule")
  for _, body in ipairs(tbl.bodies) do
    for _, row in ipairs(body.body) do
      table.insert(lines, row_latex(row))
    end
  end
  table.insert(lines, "\\bottomrule")
  table.insert(lines, "\\end{tabular}")
  table.insert(lines, "\\end{table}")
  return pandoc.RawBlock("latex", table.concat(lines, "\n"))
end
