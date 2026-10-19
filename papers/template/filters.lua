-- The Markdown links PNG figures so that it renders on GitHub; the paper takes the vector PDF beside each.
function Image(img)
  local pdf = img.src:gsub("%.png$", ".pdf")
  if pdf ~= img.src and io.open(pdf, "r") then
    img.src = pdf
  end
  return img
end

local appendix_started = false

-- A heading with the class "appendix" starts the appendices.
function Header(h)
  if appendix_started or not h.classes:includes("appendix") then
    return h
  end
  appendix_started = true
  return {pandoc.RawBlock("latex", "\\appendix"), h}
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
