
from odoo_module_upgrade.base_migration_script import BaseMigrationScript
import lxml.etree as et
from pathlib import Path
import sys
import os
import ast
from typing import Any

import re
from lxml import etree

NEW_ATTRS = ['invisible', 'required', 'readonly', 'column_invisible']

empty_list = ast.parse("[]").body[0].value

KNOWN_ODOO_MODULES = {
    # Core Odoo modules
    'base', 'web', 'mail', 'portal', 'resource', 'barcodes', 'bus', 'contacts',
    'calendar', 'crm', 'digest', 'fetchmail', 'gamification', 'hr', 'hr_attendance',
    'hr_holidays', 'hr_maintenance', 'hr_recruitment', 'hr_timesheet', 'im_livechat',
    'link_tracker', 'mass_mailing', 'note', 'phone_validation', 'rating', 'sms',
    'snailmail', 'social_media', 'survey', 'utm', 'voip', 'website',
    
    # Accounting modules
    'account', 'account_accountant', 'account_asset', 'account_budget',
    'account_check_printing', 'account_followup', 'account_invoice_extract',
    'account_payment', 'account_reports', 'account_sequence', 'account_tax_python',
    'analytic', 'payment', 'payment_adyen', 'payment_authorize', 'payment_buckaroo',
    'payment_paypal', 'payment_stripe', 'payment_transfer',
    
    # Inventory & Manufacturing
    'stock', 'stock_account', 'stock_barcode', 'stock_dropshipping', 'stock_landed_costs',
    'stock_picking_batch', 'mrp', 'mrp_account', 'mrp_bom_cost', 'mrp_byproduct',
    'mrp_mps', 'mrp_plm', 'mrp_repair', 'mrp_subcontracting', 'mrp_workorder',
    'quality', 'quality_control', 'quality_mrp', 'maintenance',
    
    # Sales & Purchase
    'sale', 'sale_management', 'sale_margin', 'sale_stock', 'sale_timesheet',
    'purchase', 'purchase_requisition', 'purchase_stock', 'pos_discount',
    'pos_hr', 'pos_mercury', 'pos_restaurant', 'point_of_sale',
    
    # Project & Services  
    'project', 'project_forecast', 'project_timesheet_holidays', 'timesheet_grid',
    'planning', 'helpdesk', 'field_service', 'industry_fsm',
    
    # Website & eCommerce
    'website_blog', 'website_crm', 'website_event', 'website_event_track',
    'website_form', 'website_forum', 'website_hr_recruitment', 'website_livechat',
    'website_mass_mailing', 'website_partner', 'website_payment', 'website_profile',
    'website_quote', 'website_sale', 'website_sale_comparison', 'website_sale_delivery',
    'website_sale_digital', 'website_sale_stock', 'website_sale_wishlist',
    'website_slides', 'website_twitter', 'website_version',
    
    # Marketing & Events
    'marketing_automation', 'event', 'event_booth', 'event_sale', 'social',
    
    # Localization modules (common ones)
    'l10n_us', 'l10n_ca', 'l10n_mx', 'l10n_eu_oss', 'l10n_generic_coa',
    
    # Other common modules
    'documents', 'sign', 'spreadsheet_dashboard', 'approvals', 'fleet',
    'lunch', 'hr_expense', 'hr_skills', 'website_appointment', 'appointment',
    'whatsapp', 'discuss', 'knowledge', 'industry_fsm_sale', 'industry_fsm_stock',
    'hr_work_entry', 'hr_work_entry_contract', 'hr_payroll', 'hr_contract',
}

IGNORE_PREFIXES = {
    'ir',           # Odoo framework (ir.model, ir.actions, etc.)
    'res',          # Resource framework (res.partner, res.users, etc.) - but 'res' itself is not a module
    'wizard',       # Wizard framework
    'report',       # Report framework  
    'workflow',     # Workflow framework (deprecated but still seen)
    'base_import',  # Import framework
    'web_editor',   # Web editor framework components
    'web_tour',     # Web tour framework
    'object',
    'record',
    'cdb',
    'general',
    'edp',
    'tc',
    'widget','mantaray','base_address_city'
}


class AbstractVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        # ((line, line_end, col_offset, end_col_offset), replace_by) NO OVERLAPS
        self.change_todo = []

    def post_process(self, all_code: str, file: str) -> str:
        all_lines = all_code.split("\n")
        for (lineno, line_end, col_offset, end_col_offset), new_substring in sorted(
            self.change_todo, reverse=True
        ):
            if lineno == line_end:
                line = all_lines[lineno - 1]
                all_lines[lineno - 1] = (
                    line[:col_offset] + new_substring + line[end_col_offset:]
                )
            else:
                print(
                    f"Ignore replacement {file}: {(lineno, line_end, col_offset, end_col_offset), new_substring}"
                )
        return "\n".join(all_lines)

    def add_change(self, old_node: ast.AST, new_node: ast.AST | str):
        position = (
            old_node.lineno,
            old_node.end_lineno,
            old_node.col_offset,
            old_node.end_col_offset,
        )
        if isinstance(new_node, str):
            self.change_todo.append((position, new_node))
        else:
            self.change_todo.append((position, ast.unparse(new_node)))


class VisitorToPrivateReadGroup(AbstractVisitor):
    def post_process(self, all_code: str, file: str) -> str:
        all_lines = all_code.split("\n")
        for i, line in enumerate(all_lines):
            if "super(" not in line:
                all_lines[i] = line.replace(".read_group(", "._read_group(")
        return "\n".join(all_lines)


class VisitorInverseGroupbyFields(AbstractVisitor):
    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "_read_group":
            # Should have the same number of args/keywords
            # Inverse fields/groupby order
            keywords_by_key = {keyword.arg: keyword.value for keyword in node.keywords}
            key_i_by_key = {keyword.arg: i for i, keyword in enumerate(node.keywords)}
            if len(node.args) >= 3:
                self.add_change(node.args[2], node.args[1])
                self.add_change(node.args[1], node.args[2])
            elif len(node.args) == 2:
                new_args_value = keywords_by_key.get("groupby", empty_list)
                if "groupby" in keywords_by_key:
                    fields_args = ast.keyword("fields", node.args[1])
                    self.add_change(node.args[1], new_args_value)
                    self.add_change(node.keywords[key_i_by_key["groupby"]], fields_args)
                else:
                    self.add_change(
                        node.args[1],
                        f"{ast.unparse(new_args_value)}, {ast.unparse(node.args[1])}",
                    )
            else:  # len(node.args) <= 2
                if (
                    "groupby" in key_i_by_key
                    and "fields" in key_i_by_key
                    and key_i_by_key["groupby"] > key_i_by_key["fields"]
                ):
                    self.add_change(
                        node.keywords[key_i_by_key["groupby"]],
                        node.keywords[key_i_by_key["fields"]],
                    )
                    self.add_change(
                        node.keywords[key_i_by_key["fields"]],
                        node.keywords[key_i_by_key["groupby"]],
                    )
                else:
                    raise ValueError(f"{key_i_by_key}, {keywords_by_key}, {node.args}")
        self.generic_visit(node)


class VisitorRenameKeywords(AbstractVisitor):
    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "_read_group":
            # Replace fields by aggregate and orderby by order
            for keyword in node.keywords:
                if keyword.arg == "fields":
                    new_keyword = ast.keyword("aggregates", keyword.value)
                    self.add_change(keyword, new_keyword)
                if keyword.arg == "orderby":
                    new_keyword = ast.keyword("order", keyword.value)
                    self.add_change(keyword, new_keyword)
        self.generic_visit(node)


class VisitorRemoveLazy(AbstractVisitor):
    def post_process(self, all_code: str, file: str) -> str:
        # remove extra comma ',' and extra line if possible
        all_code = super().post_process(all_code, file)
        all_lines = all_code.split("\n")
        for (lineno, __, col_offset, __), __ in sorted(self.change_todo, reverse=True):
            comma_find = False
            line = all_lines[lineno - 1]
            remaining = line[col_offset:]
            line = line[:col_offset]
            while not comma_find:
                if "," not in line:
                    all_lines.pop(lineno - 1)
                    lineno -= 1
                    line = all_lines[lineno - 1]
                else:
                    comma_find = True
            last_index_comma = -(line[::-1].index(",") + 1)
            all_lines[lineno - 1] = line[:last_index_comma] + remaining

        return "\n".join(all_lines)

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "_read_group":
            # Replace fields by aggregate and orderby by order
            if len(node.args) == 7:
                self.add_change(node.args[6], "")
            else:
                for keyword in node.keywords:
                    if keyword.arg == "lazy":
                        self.add_change(keyword, "")
        self.generic_visit(node)


class VisitorAggregatesSpec(AbstractVisitor):
    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "_read_group":

            keywords_by_key = {keyword.arg: keyword.value for keyword in node.keywords}
            aggregate_values = None
            if len(node.args) >= 3:
                aggregate_values = node.args[2]
            elif "aggregates" in keywords_by_key:
                aggregate_values = keywords_by_key["aggregates"]

            groupby_values = empty_list
            if len(node.args) >= 2:
                groupby_values = node.args[1]
            elif "groupby" in keywords_by_key:
                groupby_values = keywords_by_key["groupby"]

            if aggregate_values:
                aggregates = None
                try:
                    aggregates = ast.literal_eval(ast.unparse(aggregate_values))
                    if not isinstance(aggregates, (list, tuple)):
                        raise ValueError(
                            f"{aggregate_values} is not a list but literal ?"
                        )

                    aggregates = [
                        f"{field_spec.split('(')[1][:-1]}:{field_spec.split(':')[1].split('(')[0]}"
                        if "(" in field_spec
                        else field_spec
                        for field_spec in aggregates
                    ]
                    aggregates = [
                        "__count"
                        if field_spec in ("id:count", "id:count_distinct")
                        else field_spec
                        for field_spec in aggregates
                    ]

                    groupby = ast.literal_eval(ast.unparse(groupby_values))
                    if isinstance(groupby, str):
                        groupby = [groupby]

                    aggregates = [
                        f"{field}:sum"
                        if (":" not in field and field != "__count")
                        else field
                        for field in aggregates
                        if field not in groupby
                    ]
                    if not aggregates:
                        aggregates = ["__count"]
                except SyntaxError:
                    pass
                except ValueError:
                    pass

                if aggregates is not None:
                    self.add_change(aggregate_values, repr(aggregates))
        self.generic_visit(node)


Steps_visitor: list[AbstractVisitor] = [
    VisitorToPrivateReadGroup,
    VisitorInverseGroupbyFields,
    VisitorRenameKeywords,
    VisitorAggregatesSpec,
    VisitorRemoveLazy,
]


# def replace_read_group_signature(logger, filename):
#     with open(filename, mode="rt") as file:
#         new_all = all_code = file.read()
#         if ".read_group(" in all_code or "._read_group(" in all_code:
#             for Step in Steps_visitor:
#                 visitor = Step()
#                 try:
#                     visitor.visit(ast.parse(new_all))
#                 except Exception:
#                     logger.info(
#                         f"ERROR in {filename} at step {visitor.__class__}: \n{new_all}"
#                     )
#                     raise
#                 new_all = visitor.post_process(new_all, filename)
#             if new_all == all_code:
#                 logger.info("read_group detected but not changed in file %s" % filename)

#     if new_all != all_code:
#         logger.info("Script read_group replace applied in file %s" % filename)
#         with open(filename, mode="wt") as file:
#             file.write(new_all)

def replace_read_group_signature(logger, filename):
    # Try different encodings to handle various file encodings
    encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
    
    content = None
    used_encoding = None
    
    for encoding in encodings_to_try:
        try:
            with open(filename, mode="rt", encoding=encoding) as file:
                content = file.read()
                used_encoding = encoding
                break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"Unexpected error reading {filename} with encoding {encoding}: {e}")
            continue
    
    if content is None:
        logger.error(f"Could not read file {filename} with any of the tried encodings: {encodings_to_try}")
        return
    
    all_code = content
    new_all = all_code
    
    if ".read_group(" in all_code or "._read_group(" in all_code:
        for Step in Steps_visitor:
            visitor = Step()
            try:
                visitor.visit(ast.parse(new_all))
            except Exception:
                logger.info(
                    f"ERROR in {filename} at step {visitor.__class__}: \n{new_all}"
                )
                raise
            new_all = visitor.post_process(new_all, filename)
        if new_all == all_code:
            logger.info("read_group detected but not changed in file %s" % filename)

    if new_all != all_code:
        logger.info("Script read_group replace applied in file %s" % filename)
        try:
            with open(filename, mode="wt", encoding=used_encoding) as file:
                file.write(new_all)
        except Exception as e:
            logger.error(f"Error writing back to {filename}: {e}")
            # Fallback to UTF-8 if the original encoding fails
            try:
                with open(filename, mode="wt", encoding='utf-8') as file:
                    file.write(new_all)
                logger.info(f"File {filename} written using UTF-8 encoding as fallback")
            except Exception as fallback_error:
                logger.error(f"Failed to write {filename} even with UTF-8 fallback: {fallback_error}")


def _get_files(module_path, reformat_file_ext):
    """Get files to be reformatted."""
    file_paths = list()
    if not module_path.is_dir():
        raise Exception(f"'{module_path}' is not a directory")
    file_paths.extend(module_path.rglob("*" + reformat_file_ext))
    return file_paths


def _check_open_form_view(logger, file_path: Path):
    """Check if the view has a button to open a form reg in a tree view `file_path`."""
    parser = et.XMLParser(remove_blank_text=True)
    tree = et.parse(str(file_path.resolve()), parser)
    record_node = tree.getroot()[0]
    f_arch = record_node.find('field[@name="arch"]')
    root = f_arch if f_arch is not None else record_node
    for button in root.findall(".//button[@name='get_formview_action']"):
        logger.warning(
            (
                "Button to open a form reg form a tree view detected in file %s line %s, probably should be changed by open_form_view='True'. More info here https://github.com/odoo/odoo/commit/258e6a019a21042bf4f6cf70fcce386d37afd50c"
            )
            % (file_path.name, button.sourceline)
        )


def _check_open_form(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    reformat_file_ext = ".xml"
    file_paths = _get_files(module_path, reformat_file_ext)
    logger.debug(f"{reformat_file_ext} files found:\n" f"{list(map(str, file_paths))}")

    for file_path in file_paths:
        _check_open_form_view(logger, file_path)


def _reformat_read_group(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    """Reformat read_group method in py files."""

    reformat_file_ext = ".py"
    file_paths = _get_files(module_path, reformat_file_ext)
    logger.debug(f"{reformat_file_ext} files found:\n" f"{list(map(str, file_paths))}")

    reformatted_files = list()
    for file_path in file_paths:
        reformatted_file = replace_read_group_signature(logger, file_path)
        if reformatted_file:
            reformatted_files.append(reformatted_file)
    logger.debug("Reformatted files:\n" f"{list(reformatted_files)}")

def normalize_domain(domain):
    """
    Normalize Domain, taken from odoo/osv/expression.py -> just the part so that & operators are added where needed.
    After that, we can use a part of the def parse() from the same file to manage parenthesis for and/or

    :rtype: list[str|tuple]
    """
    if len(domain) == 1:
        return domain
    result = []
    expected = 1  # expected number of expressions
    op_arity = {'!': 1, '&': 2, '|': 2}
    for token in domain:
        if expected == 0:  # more than expected, like in [A, B]
            result[0:0] = ['&']  # put an extra '&' in front
            expected = 1
        if isinstance(token, (list, tuple)):  # domain term
            expected -= 1
            token = tuple(token)
        else:
            expected += op_arity.get(token, 0) - 1
        result.append(token)
    return result

def stringify_leaf(leaf):
    """
    :param tuple leaf:
    :rtype: str
    """
    stringify = ''
    switcher = False
    case_insensitive = False
    # Replace operators not supported in python (=, like, ilike)
    operator = str(leaf[1])
    # Take left operand, never to add quotes (should be python object / field)
    left_operand = leaf[0]
    # Take care of right operand, don't add quotes if it's list/tuple/set/boolean/number, check if we have a true/false/1/0 string tho.
    right_operand = leaf[2]

    # Handle '=?'
    if operator == '=?':
        if type(right_operand) is str:
            right_operand = f"'{right_operand}'"
        return f"({right_operand} in [None, False] or {left_operand} == {right_operand})"
    # Handle '='
    elif operator == '=':
        if right_operand in (False, []):  # Check for False or empty list
            return f"not {left_operand}"
        elif right_operand == True:  # Check for True using '==' comparison so only boolean values can evaluate to True
            return left_operand
        operator = '=='
    # Handle '!='
    elif operator == '!=':
        if right_operand in (False, []):  # Check for False or empty list
            return left_operand
        elif right_operand == True:  # Check for True using '==' comparison so only boolean values can evaluate to True
            return f"not {left_operand}"
    # Handle 'like' and other operators
    elif 'like' in operator:
        case_insensitive = 'ilike' in operator
        if type(right_operand) is str and re.search('[_%]', right_operand):
            # Since wildcards won't work/be recognized after conversion we throw an error so we don't end up with
            # expressions that behave differently from their originals
            raise Exception("Script doesn't support 'like' domains with wildcards")
        if operator in ['=like', '=ilike']:
            operator = '=='
        else:
            if 'not' in operator:
                operator = 'not in'
            else:
                operator = 'in'
            switcher = True
    if type(right_operand) is str:
        right_operand = f"'{right_operand}'"
    if switcher:
        temp_operand = left_operand
        left_operand = right_operand
        right_operand = temp_operand
    if not case_insensitive:
        stringify = f"{left_operand} {operator} {right_operand}"
    else:
        stringify = f"{left_operand}.lower() {operator} {right_operand}.lower()"
    return stringify


def stringify_attr(stack):
    """
    :param bool|str|int|list stack:
    :rtype: str
    """
    if stack in (True, False, 'True', 'False', 1, 0, '1', '0'):
        return str(stack)
    last_parenthesis_index = max(index for index, item in enumerate(stack[::-1]) if item not in ('|', '!'))
    stack = normalize_domain(stack)
    stack = stack[::-1]
    result = []
    for index, leaf_or_operator in enumerate(stack):
        if leaf_or_operator == '!':
            expr = result.pop()
            result.append('(not (%s))' % expr)
        elif leaf_or_operator in ['&', '|']:
            left = result.pop()
            # In case of a single | or single & , we expect that it's a tag that have an attribute AND a state
            # the state will be added as OR in states management
            try:
                right = result.pop()
            except IndexError:
                res = left + ('%s' % ' and' if leaf_or_operator == '&' else ' or')
                result.append(res)
                continue
            form = '(%s %s %s)'
            if index > last_parenthesis_index:
                form = '%s %s %s'
            result.append(form % (left, 'and' if leaf_or_operator == '&' else 'or', right))
        else:
            result.append(stringify_leaf(leaf_or_operator))
    result = result[0]
    return result


def get_new_attrs(attrs):
    """
    :param str attrs:
    :rtype: dict[bool|str|int]
    """
    new_attrs = {}
    # Temporarily replace dynamic variables (field reference, context value, %()d) in leafs by strings prefixed with '__dynamic_variable__.'
    # This way the evaluation won't fail on these strings, and we can later identify them to convert back to  their original values
    escaped_operators = ['=', '!=', '>', '>=', '<', '<=', '=\\?', '=like', 'like', 'not like', 'ilike', 'not ilike', '=ilike', 'in', 'not in', 'child_of', 'parent_of']
    attrs = re.sub("&lt;", "<", attrs)
    attrs = re.sub("&gt;", ">", attrs)
    attrs = re.sub(r"([\"'](?:{'|'.join(escaped_operators)})[\"']\s*,\s*)(?!False|True)([\w\.]+)(?=\s*[\]\)])", r"\1'__dynamic_variable__.\2'", attrs)
    attrs = re.sub(r"(%\([\w\.]+\)d)", r"'__dynamic_variable__.\1'", attrs)
    attrs = attrs.strip()
    if re.search("^{.*}$", attrs, re.DOTALL):
        # attrs can be an empty value, in which case the eval() would fail, so only eval attrs representing dictionaries
        attrs_dict = eval(attrs.strip())
        for attr, attr_value in attrs_dict.items():
            if attr not in NEW_ATTRS:
                # We don't know what to do with attributes not in NEW_ATTR, so the user will have to process those
                # manually when checking the differences post-conversion
                continue
            stringified_attr = stringify_attr(attr_value)
            if type(stringified_attr) is str:
                # Convert dynamic variable strings back to their original form
                stringified_attr = re.sub(r"'__dynamic_variable__\.([^']+)'", r"\1", stringified_attr)
            new_attrs[attr] = stringified_attr
    return new_attrs

def get_parent_etree_node(root_node, target_node):
    """
    Returns the parent node of a given node, and the index and indentation of the target node in the parent node's direct child nodes list

    :param xml.etree.ElementTree.Element root_node:
    :param xml.etree.ElementTree.Element target_node:
    :returns: index, parent_node, indentation
    :rtype: (int, xml.etree.ElementTree.Element, str)
    """
    for parent_elem in root_node.iter():
        previous_child = False
        for i, child in enumerate(list(parent_elem)):
            if child == target_node:
                if previous_child:
                    indent = previous_child.tail
                else:
                    # For the first child element it's the text in between the parent's opening tag and the first child that determines indentation
                    indent = parent_elem.text
                return i, parent_elem, indent
            previous_child = child

def get_child_tag_at_index(parent_node, index):
    """
    Returns the child node of a node with a given index

    :param xml.etree.ElementTree.Element parent_node:
    :param int index:
    :returns: child_node
    :rtype: xml.etree.ElementTree.Element
    """
    for i, child in enumerate(list(parent_node)):
        if i == index:
            return child


def get_sibling_attribute_tag_of_type(root_node, target_node, attribute_name):
    """
    If it exists, returns the attribute tag with the same parent tag for the given name

    :param xml.etree.ElementTree.Element root_node:
    :param xml.etree.ElementTree.Element target_node:
    :param str attribute_name:
    :returns: attribute_tag with name="<attribute_name>"
    :rtype: xml.etree.ElementTree.Element
    """
    _, xpath_node, _ = get_parent_etree_node(root_node, target_node)
    if node := xpath_node.xpath(f"./attribute[@name='{attribute_name}']"):
        return node[0]


def get_inherited_tag_type(root_node, target_node):
    """
    Checks what the type of the tag is that the attribute tag applies to

    :param xml.etree.ElementTree.Element root_node:
    :param xml.etree.ElementTree.Element target_node:
    :rtype: str|None
    """
    _, parent_tag, _ = get_parent_etree_node(root_node, target_node)
    if expr := parent_tag.get('expr'):
        # Checks if the last part of the xpath expression is a tag name and returns it
        # If not (eg. if the pattern is for example expr="//field[@name='...']/.."), return None
        if matches := re.findall(r"^.*/(\w+)[^/]*?$", expr):
            return matches[0]
    else:
        return parent_tag.tag

def get_combined_invisible_condition(invisible_attribute, states_attribute):
    """
    :param str invisible_attribute: invisible attribute condition already present on the same tag as the states
    :param str states_attribute: string of the form 'state1,state2,...'
    """
    invisible_attribute = invisible_attribute.strip()
    states_attribute = states_attribute.strip()
    if not states_attribute:
        return invisible_attribute
    states_list = re.split(r"\s*,\s*", states_attribute.strip())
    states_to_add = f"state not in {states_list}"
    if invisible_attribute:
        if invisible_attribute.endswith('or') or invisible_attribute.endswith('and'):
            combined_invisible_condition = f"{invisible_attribute} {states_to_add}"
        else:
            combined_invisible_condition = f"{invisible_attribute} or {states_to_add}"
    else:
        combined_invisible_condition = states_to_add
    return combined_invisible_condition


def replace_attrs_expressions(logger, module_path, module_name, manifest_path, migration_steps, tools):
    """Replace complex attrs expressions with simplified versions."""
    files_to_process = tools.get_files(module_path, (".xml",))

    for file in files_to_process:
        try:
            with open(file, 'rb') as f:
                content = f.read().decode('utf-8')
                f.close()
                if not 'attrs' in content and not 'states' in content:
                    continue
                convert_line_separator_back_to_windows = False
                if '\r\n' in content:
                    convert_line_separator_back_to_windows = True
                has_encoding_declaration = False
                if encoding_declaration := re.search(r"\A.*<\?xml.*?encoding=.*?\?>\s*", content, re.DOTALL):
                    has_encoding_declaration = True
                    content = re.sub(r"\A.*<\?xml.*?encoding=.*?\?>\s*", "", content, re.DOTALL)
                doc = etree.fromstring(content)
                tags_with_attrs = doc.xpath("//*[@attrs]")
                attribute_tags_with_attrs = doc.xpath("//attribute[@name='attrs']")
                tags_with_states = doc.xpath("//*[@states]")
                attribute_tags_with_states = doc.xpath("//attribute[@name='states']")
                if not (tags_with_attrs or attribute_tags_with_attrs or tags_with_states or attribute_tags_with_states):
                    continue
                for t in tags_with_attrs + attribute_tags_with_attrs + tags_with_states + attribute_tags_with_states:
                    logger.info(etree.tostring(t, encoding='unicode'))
                nofilesfound = False
                for tag in tags_with_attrs:
                    all_attributes = []
                    attrs = tag.get('attrs', '')
                    new_attrs = get_new_attrs(attrs)
                    for attr_name, attr_value in list(tag.attrib.items()):
                        if attr_name == 'attrs':
                            for new_attr, new_attr_value in new_attrs.items():
                                if new_attr in tag.attrib:
                                    old_attr_value = tag.attrib.get(new_attr)
                                    if old_attr_value in [True, 1, 'True', '1']:
                                        new_attr_value = f"True or ({new_attr_value})"
                                    elif old_attr_value in [False, 0, 'False', '0']:
                                        new_attr_value = f"False or ({new_attr_value})"
                                    else:
                                        new_attr_value = f"({old_attr_value}) or ({new_attr_value})"
                                all_attributes.append((new_attr, new_attr_value))
                        elif attr_name not in new_attrs:
                            all_attributes.append((attr_name, attr_value))
                    tag.attrib.clear()
                    tag.attrib.update(all_attributes)

                attribute_tags_with_attrs_after = []
                for attribute_tag in attribute_tags_with_attrs:
                    tag_type = get_inherited_tag_type(doc, attribute_tag)
                    tag_index, parent_tag, indent = get_parent_etree_node(doc, attribute_tag)
                    tail = attribute_tag.tail or ''
                    attrs = attribute_tag.text or ''
                    new_attrs = get_new_attrs(attrs)
                    attribute_tags_to_remove = []
                    for new_attr, new_attr_value in new_attrs.items():
                        if (
                        separate_attr_tag := get_sibling_attribute_tag_of_type(doc, attribute_tag, new_attr)) is not None:
                            attribute_tags_to_remove.append(separate_attr_tag)
                            old_attr_value = separate_attr_tag.text
                            if old_attr_value in [True, 1, 'True', '1']:
                                new_attr_value = f"True or ({new_attr_value})"
                            elif old_attr_value in [False, 0, 'False', '0']:
                                new_attr_value = f"False or ({new_attr_value})"
                            else:
                                new_attr_value = f"({old_attr_value}) or ({new_attr_value})"
                        new_tag = etree.Element('attribute', attrib={
                            'name': new_attr
                        })
                        new_tag.text = str(new_attr_value)
                        new_tag.tail = indent
                        parent_tag.insert(tag_index, new_tag)
                        if new_attr == 'invisible':
                            if get_sibling_attribute_tag_of_type(doc, new_tag, 'states') is None:
                                todo_tag = etree.Comment(
                                    f"TODO: Result from 'attrs' -> 'invisible' conversion without also overriding 'states' attribute"
                                    f"{indent + (' ' * 5)}Check if this {tag_type + ' ' if tag_type else ''}tag contained a states attribute in any of the parent views, in which case it should be combined into this 'invisible' attribute"
                                    f"{indent + (' ' * 5)}(If any states attributes existed in parent views, they'll also be marked with a TODO)")
                                todo_tag.tail = indent
                                parent_tag.insert(tag_index, todo_tag)
                                attribute_tags_with_attrs_after.append(todo_tag)
                                tag_index += 1
                        attribute_tags_with_attrs_after.append(new_tag)
                        tag_index += 1
                    missing_attrs = []
                    if tag_type == 'field':
                        potentially_missing_attrs = NEW_ATTRS
                    else:
                        potentially_missing_attrs = ['invisible']
                    for missing_attr in potentially_missing_attrs:
                        if missing_attr not in new_attrs and get_sibling_attribute_tag_of_type(doc, attribute_tag,
                                                                                               missing_attr) is None:
                            missing_attrs.append(missing_attr)
                    if missing_attrs:
                        if tag_type == 'field':
                            new_tag = etree.Comment(
                                f"TODO: Result from converting 'attrs' attribute override without options for {missing_attrs} to separate attributes"
                                f"{indent + (' ' * 5)}Remove redundant empty tags below for any of those attributes that are not present in the field tag in any of the parent views"
                                f"{indent + (' ' * 5)}If someone later adds one of these attributes in the parent views, they would likely be unaware it's still overridden in this view, resulting in unexpected behaviour, which should be avoided")
                            new_tag.tail = indent
                            parent_tag.insert(tag_index, new_tag)
                            attribute_tags_with_attrs_after.append(new_tag)
                            tag_index += 1
                        else:
                            pass
                        for missing_attr in missing_attrs:
                            new_tag = etree.Element('attribute', attrib={
                                'name': missing_attr
                            })
                            new_tag.tail = indent
                            parent_tag.insert(tag_index, new_tag)
                            if missing_attr == 'invisible':
                                if get_sibling_attribute_tag_of_type(doc, new_tag, 'states') is None:
                                    todo_tag = etree.Comment(
                                        f"TODO: Result from 'attrs' -> 'invisible' conversion without also overriding 'states' attribute"
                                        f"{indent + (' ' * 5)}Check if this {tag_type + ' ' if tag_type else ''}tag contained a states attribute in any of the parent views, that should be combined into this 'invisible' attribute"
                                        f"{indent + (' ' * 5)}(If any states attributes existed in parent views, they'll also be marked with a TODO)")
                                    todo_tag.tail = indent
                                    parent_tag.insert(tag_index, todo_tag)
                                    attribute_tags_with_attrs_after.append(todo_tag)
                                    tag_index += 1
                            attribute_tags_with_attrs_after.append(new_tag)
                            tag_index += 1
                    new_tag.tail = tail
                    parent_tag.remove(attribute_tag)
                    for attribute_tag_to_remove in attribute_tags_to_remove:
                        tag_index, parent_tag, indent = get_parent_etree_node(doc, attribute_tag_to_remove)
                        if tag_index > 0:
                            previous_tag = get_child_tag_at_index(parent_tag, tag_index - 1)
                            previous_tag.tail = attribute_tag_to_remove.tail
                            parent_tag.remove(attribute_tag_to_remove)

                for state_tag in tags_with_states:
                    states_attribute = state_tag.get('states', '')
                    invisible_attribute = state_tag.get('invisible', '')
                    tag_index, parent_tag, indent = get_parent_etree_node(doc, state_tag)
                    if invisible_attribute:
                        conversion_action_string = f"Result from merging \"states='{states_attribute}'\" attribute with an 'invisible' attribute"
                    else:
                        conversion_action_string = f"Result from converting \"states='{states_attribute}'\" attribute into an 'invisible' attribute"
                    todo_tag = etree.Comment(
                        f"TODO: {conversion_action_string}"
                        f"{indent + (' ' * 5)}Manually combine states condition into any 'invisible' overrides in inheriting views as well")
                    todo_tag.tail = indent
                    parent_tag.insert(tag_index, todo_tag)

                    new_invisible_attribute = get_combined_invisible_condition(invisible_attribute, states_attribute)
                    all_attributes = []
                    for attr_name, attr_value in list(state_tag.attrib.items()):
                        if attr_name == 'invisible' or (attr_name == 'states' and not invisible_attribute):
                            if new_invisible_attribute:
                                all_attributes.append(('invisible', new_invisible_attribute))
                        elif attr_name != 'states':
                            all_attributes.append((attr_name, attr_value))
                    state_tag.attrib.clear()
                    state_tag.attrib.update(all_attributes)

                attribute_tags_with_states_after = []
                for attribute_tag_states in attribute_tags_with_states:
                    tag_type = get_inherited_tag_type(doc, attribute_tag_states)
                    tag_index, parent_tag, indent = get_parent_etree_node(doc, attribute_tag_states)
                    tail = attribute_tag_states.tail
                    attribute_tag_invisible = get_sibling_attribute_tag_of_type(doc, attribute_tag_states, 'invisible')
                    if attribute_tag_invisible is not None:
                        if tag_index > 0:
                            previous_tag = get_child_tag_at_index(parent_tag, tag_index - 1)
                            previous_tag.tail = attribute_tag_states.tail
                    else:
                        todo_tag = etree.Comment(
                            f"TODO: Result from \"states='{states_attribute}'\" -> 'invisible' conversion without also overriding 'attrs' attribute"
                            f"{indent + (' ' * 5)}Check if this {tag_type + ' ' if tag_type else ''}tag contains an invisible attribute in any of the parent views, in which case it should be combined into this new 'invisible' attribute"
                            f"{indent + (' ' * 5)}(Only applies to invisible attributes in the parent views that were not originally states attributes. Those from converted states attributes will be marked with a TODO)")
                        todo_tag.tail = indent
                        parent_tag.insert(tag_index, todo_tag)
                        attribute_tags_with_states_after.append(todo_tag)
                        tag_index += 1
                        attribute_tag_invisible = etree.Element('attribute', attrib={'name': 'invisible'})
                        attribute_tag_invisible.tail = tail
                        parent_tag.insert(tag_index, attribute_tag_invisible)

                    invisible_attribute = attribute_tag_invisible.text or ''
                    states_attribute = attribute_tag_states.text or ''
                    invisible_condition = get_combined_invisible_condition(invisible_attribute, states_attribute)
                    parent_tag.remove(attribute_tag_states)
                    attribute_tag_invisible.text = invisible_condition
                    attribute_tags_with_states_after.append(attribute_tag_invisible)
                for t in tags_with_attrs + attribute_tags_with_attrs_after + tags_with_states + attribute_tags_with_states_after:
                    logger.info(etree.tostring(t, encoding='unicode'))
                with open(file, 'wb') as rf:
                    xml_string = etree.tostring(doc, encoding='utf-8', xml_declaration=has_encoding_declaration)
                    if convert_line_separator_back_to_windows:
                        xml_string = xml_string.replace(b"\n", b"\r\n")
                    rf.write(xml_string)
                if content != xml_string:
                    logger.info(f"Updated attrs expressions in {file}")
        except Exception as e:
            logger.error(f"Error processing file {file}: {str(e)}")

def _find_manifest_file(module_path):
    """Find the manifest file (__manifest__.py) in the module."""
    manifest_paths = [
        module_path / "__manifest__.py",
        module_path / "__openerp__.py",
    ]    
    for manifest_path in manifest_paths:
        if manifest_path.exists():
            return manifest_path    
    return None


# def _update_manifest_version(logger, module_path, module_name, manifest_path, migration_steps, tools):
#     """Update manifest version to be compatible with Odoo 17."""
#     manifest_file = _find_manifest_file(module_path)
    
#     if not manifest_file:
#         logger.warning(f"No manifest file found in module {module_name}")
#         return
    
#     try:
#         with open(manifest_file, 'r', encoding='utf-8') as f:
#             content = f.read()
        
#         try:
#             tree = ast.parse(content)
#             if not tree.body or not isinstance(tree.body[0], ast.Assign):
#                 raise ValueError("Manifest file doesn't contain a proper assignment")
            
#             local_vars = {}
#             exec(content, {}, local_vars)
            
#             manifest_dict = None
#             for var_name, var_value in local_vars.items():
#                 if isinstance(var_value, dict) and 'name' in var_value:
#                     manifest_dict = var_value
#                     break
            
#             if not manifest_dict:
#                 logger.warning(f"Could not find manifest dictionary in {manifest_file}")
#                 return
            
#             original_version = manifest_dict.get('version', '1.0.0')
            
#             version_parts = original_version.split('.')
#             if len(version_parts) >= 2:
#                 if version_parts[0] != '17' or version_parts[1] != '0':
#                     if len(version_parts) >= 3:
#                         new_version = f"17.0.{version_parts[2]}"
#                         if len(version_parts) > 3:
#                             new_version += f".{'.'.join(version_parts[3:])}"
#                     else:
#                         new_version = "17.0.1.0.0"
#                 else:
#                     new_version = original_version
#             else:
#                 new_version = "17.0.1.0.0"
            
#             updated_content = re.sub(
#                 r"('version'\s*:\s*['\"])[^'\"]+(['\"])",
#                 rf"\g<1>{new_version}\g<2>",
#                 content
#             )
            
#             updated_content = re.sub(
#                 r'("version"\s*:\s*["\'])[^"\']+(["\'])',
#                 rf'\g<1>{new_version}\g<2>',
#                 updated_content
#             )
            
#             if updated_content != content:
#                 with open(manifest_file, 'w', encoding='utf-8') as f:
#                     f.write(updated_content)
#                 logger.info(f"Updated manifest version from '{original_version}' to '{new_version}' in {manifest_file}")
#             else:
#                 logger.info(f"Manifest version '{original_version}' already compatible with Odoo 17 in {manifest_file}")
                
#         except Exception as e:
#             logger.error(f"Error parsing manifest file {manifest_file}: {str(e)}")
            
#     except Exception as e:
#         logger.error(f"Error reading manifest file {manifest_file}: {str(e)}")

def _update_manifest_version_for_v17(logger, module_path, module_name, manifest_path, migration_steps, tools):
    """Update manifest version to be compatible with Odoo 17."""
    manifest_file = _find_manifest_file(module_path)
    
    if not manifest_file:
        logger.warning(f"No manifest file found in module {module_name}")
        return
    
    try:
        with open(manifest_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            version_match = re.search(r'["\']version["\']\s*:\s*["\']([^"\']+)["\']', content)
            if not version_match:
                logger.warning(f"Could not find version key in manifest file {manifest_file}")
                return
            
            original_version = version_match.group(1)
            
            version_parts = original_version.split('.')
            if len(version_parts) >= 2:
                if version_parts[0] != '17' or version_parts[1] != '0':
                    if len(version_parts) >= 3:
                        new_version = f"17.0.{version_parts[2]}"
                        if len(version_parts) > 3:
                            new_version += f".{'.'.join(version_parts[3:])}"
                    else:
                        new_version = "17.0.1.0.0"
                else:
                    new_version = original_version
            else:
                new_version = "17.0.1.0.0"
            
            if original_version == new_version:
                logger.info(f"Manifest version '{original_version}' already compatible with Odoo 17 in {manifest_file}")
                return
            
            updated_content = re.sub(
                r'(["\']version["\']\s*:\s*["\'])[^"\']+(["\'])',
                rf'\g<1>{new_version}\g<2>',
                content
            )
            
            if updated_content != content:
                with open(manifest_file, 'w', encoding='utf-8') as f:
                    f.write(updated_content)
                logger.info(f"Updated manifest version from '{original_version}' to '{new_version}' in {manifest_file}")
            else:
                logger.warning(f"Failed to update version in {manifest_file}")
                
        except Exception as e:
            logger.error(f"Error processing manifest file {manifest_file}: {str(e)}")
            
    except Exception as e:
        logger.error(f"Error reading manifest file {manifest_file}: {str(e)}")

def _replace_config_settings_xpath(logger, module_path, module_name, manifest_path, migration_steps, tools):
    """Replace xpath expressions specifically for res.config.settings inheritance."""
    files_to_process = tools.get_files(module_path, (".xml",))

    for file in files_to_process:
        try:
            with open(file, 'rb') as f:
                content = f.read().decode('utf-8')
                
            if not any(pattern in content for pattern in [
                'res.config.settings', 
                'base.res_config_settings_view_form',
                'res_config_settings'
            ]):
                continue
                
            original_content = content
            
            # More specific pattern that looks for the context
            patterns_to_replace = [
                # Standard single quotes
                (r'expr="//div\[hasclass\(\'settings\'\)\]"', r'expr="//form"'),
                # Standard double quotes  
                (r'expr="//div\[hasclass\("settings"\)\]"', r'expr="//form"'),
                # With additional whitespace
                (r'expr\s*=\s*"//div\[hasclass\(\s*\'settings\'\s*\)\]"', r'expr="//form"'),
                (r'expr\s*=\s*"//div\[hasclass\(\s*"settings"\s*\)\]"', r'expr="//form"'),
            ]
            
            for pattern, replacement in patterns_to_replace:
                content = re.sub(pattern, replacement, content)
            
            if content != original_content:
                with open(file, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"Replaced settings xpath expressions in {file}")
                
        except Exception as e:
            logger.error(f"Error processing file {file}: {str(e)}")

def _comment_assets_js_xml_files(logger, module_path, module_name, manifest_path, migration_steps, tools):
    """Comment out .js and .xml files in assets blocks of manifest files and log the changes."""
    manifest_file = _find_manifest_file(module_path)
    
    if not manifest_file:
        logger.warning(f"No manifest file found in module {module_name}")
        return
    
    try:
        # Try different encodings to handle various file encodings
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
        
        content = None
        used_encoding = None
        
        for encoding in encodings_to_try:
            try:
                with open(manifest_file, mode="rt", encoding=encoding) as file:
                    content = file.read()
                    used_encoding = encoding
                    break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error reading {manifest_file} with encoding {encoding}: {e}")
                continue
        
        if content is None:
            logger.error(f"Could not read manifest file {manifest_file} with any of the tried encodings: {encodings_to_try}")
            return
        
        original_content = content
        
        # Check if there's an assets block
        if 'assets' not in content:
            logger.info(f"No assets block found in manifest file {manifest_file}")
            return
        
        # Find and process assets block
        assets_pattern = r'["\']assets["\']\s*:\s*{([^{}]*(?:{[^{}]*}[^{}]*)*)}'
        assets_matches = list(re.finditer(assets_pattern, content, re.DOTALL))
        
        if not assets_matches:
            logger.info(f"No assets block structure found in manifest file {manifest_file}")
            return
        
        commented_files = []
        modified_content = content
        
        # Process each assets block (usually just one)
        for assets_match in reversed(assets_matches):  # Process in reverse to maintain string positions
            assets_content = assets_match.group(1)
            assets_start = assets_match.start(1)
            assets_end = assets_match.end(1)
            
            # Find all .js and .xml file references in the assets block
            # Pattern to match file paths ending with .js or .xml
            file_pattern = r'(["\'][^"\']*\.(?:js|xml)["\'])'
            
            lines = assets_content.split('\n')
            modified_lines = []
            
            for line_num, line in enumerate(lines):
                original_line = line
                file_matches = list(re.finditer(file_pattern, line))
                
                if file_matches:
                    # Check if line is already commented
                    stripped_line = line.strip()
                    if not (stripped_line.startswith('#') or stripped_line.startswith('//')):
                        # Find the indentation of the line
                        indent_match = re.match(r'^(\s*)', line)
                        indent = indent_match.group(1) if indent_match else ''
                        
                        # Comment out the line
                        commented_line = f"{indent}# {line.lstrip()}"
                        modified_lines.append(commented_line)
                        
                        # Log the files found in this line
                        for file_match in file_matches:
                            file_path = file_match.group(1).strip('"\'')
                            commented_files.append(file_path)
                            logger.info(f"Commented out asset file: {file_path} in {manifest_file}")
                    else:
                        # Line is already commented, keep as is
                        modified_lines.append(line)
                        logger.info(f"Asset file already commented in line: {line.strip()}")
                else:
                    # No .js or .xml files in this line, keep as is
                    modified_lines.append(line)
            
            # Replace the assets block content with modified content
            modified_assets_content = '\n'.join(modified_lines)
            modified_content = (
                modified_content[:assets_start] + 
                modified_assets_content + 
                modified_content[assets_end:]
            )
        
        # Write the modified content back to the file if changes were made
        if modified_content != original_content:
            try:
                with open(manifest_file, mode="wt", encoding=used_encoding) as file:
                    file.write(modified_content)
                
                logger.info(f"Successfully commented out {len(commented_files)} asset files in {manifest_file}")
                logger.info(f"Commented files: {commented_files}")
                
            except Exception as e:
                logger.error(f"Error writing back to {manifest_file}: {e}")
                # Fallback to UTF-8 if the original encoding fails
                try:
                    with open(manifest_file, mode="wt", encoding='utf-8') as file:
                        file.write(modified_content)
                    logger.info(f"File {manifest_file} written using UTF-8 encoding as fallback")
                except Exception as fallback_error:
                    logger.error(f"Failed to write {manifest_file} even with UTF-8 fallback: {fallback_error}")
        else:
            logger.info(f"No .js or .xml files found to comment in assets block of {manifest_file}")
            
    except Exception as e:
        logger.error(f"Error processing manifest file {manifest_file}: {str(e)}")

def _get_xml_files(module_path):
    """Get all XML files in the module."""
    xml_files = []
    if not module_path.is_dir():
        raise Exception(f"'{module_path}' is not a directory")
    xml_files.extend(module_path.rglob("*.xml"))
    return xml_files

def _is_valid_odoo_module(module_name, logger):
    """
    Check if a module name refers to a valid Odoo module that should be added as dependency.
    
    Args:
        module_name: The module name to check
        logger: Logger instance for logging decisions
        
    Returns:
        bool: True if it's a valid module, False if it should be ignored
    """
    # Check if it's in the ignore list
    if module_name in IGNORE_PREFIXES:
        logger.debug(f"Ignoring framework reference: {module_name}")
        return False
    
    # Check if it's a known Odoo module
    if module_name in KNOWN_ODOO_MODULES:
        logger.debug(f"Valid Odoo module found: {module_name}")
        return True
    
    # Log unknown modules for manual review
    logger.warning(f"Unknown module reference found: {module_name} - Please verify if this is a valid Odoo module")
    # For unknown modules, we'll be conservative and include them, but log a warning
    return True

def _extract_module_references_from_xml(xml_file, logger):
    """Extract module references from XML file content."""
    module_references = set()
    
    try:
        # Try different encodings to handle various file encodings
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
        
        content = None
        for encoding in encodings_to_try:
            try:
                with open(xml_file, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error reading {xml_file} with encoding {encoding}: {e}")
                continue
        
        if content is None:
            logger.error(f"Could not read XML file {xml_file} with any encoding")
            return module_references
        
        # Common patterns to find module references in XML files
        patterns = [
            # Pattern for module.model_name or module.action_name references
            r'(?:parent|action|model|res_model|view_id|inherit_id|ref)=["\']([a-zA-Z_][a-zA-Z0-9_]*?)\.([a-zA-Z_][a-zA-Z0-9_]*?)["\']',
            # Pattern for xpath expressions with module references  
            r'expr=["\'][^"\']*//[^/]*\[@[^@]*ref=["\']([a-zA-Z_][a-zA-Z0-9_]*?)\.([a-zA-Z_][a-zA-Z0-9_]*?)["\'][^"\']*["\']',
            # Pattern for model references
            r'<record[^>]+model=["\']([a-zA-Z_][a-zA-Z0-9_]*?)\.([a-zA-Z_][a-zA-Z0-9_]*?)["\']',
            # Pattern for field references with module prefix
            r'<field[^>]+ref=["\']([a-zA-Z_][a-zA-Z0-9_]*?)\.([a-zA-Z_][a-zA-Z0-9_]*?)["\']',
        ]
        
        raw_module_references = set()
        
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple) and len(match) >= 1:
                    module_name = match[0]
                    # Filter out common non-module references
                    if module_name not in ['self', 'parent', 'context', 'request', 'env'] and not module_name.startswith('_'):
                        raw_module_references.add(module_name)
        
        # Additional pattern for menu parent references like "project.menu_project_config"
        menu_pattern = r'parent=["\']([a-zA-Z_][a-zA-Z0-9_]*?)\.([a-zA-Z_][a-zA-Z0-9_]*?)["\']'
        menu_matches = re.findall(menu_pattern, content)
        for match in menu_matches:
            module_name = match[0]
            if module_name not in ['self', 'parent', 'context', 'request', 'env'] and not module_name.startswith('_'):
                raw_module_references.add(module_name)
        
        # Filter out invalid/framework modules
        for module_name in raw_module_references:
            if _is_valid_odoo_module(module_name, logger):
                module_references.add(module_name)
            else:
                logger.info(f"Ignored non-module reference '{module_name}' in {xml_file.name}")
        
        logger.debug(f"Valid module references in {xml_file.name}: {module_references}")
        
    except Exception as e:
        logger.error(f"Error parsing XML file {xml_file}: {str(e)}")
    
    return module_references

def _get_manifest_dependencies(manifest_file, logger):
    """Extract current dependencies from manifest file."""
    dependencies = []
    
    try:
        # Try different encodings to handle various file encodings
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
        
        content = None
        for encoding in encodings_to_try:
            try:
                with open(manifest_file, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error reading {manifest_file} with encoding {encoding}: {e}")
                continue
        
        if content is None:
            logger.error(f"Could not read manifest file {manifest_file} with any encoding")
            return dependencies
        
        # Parse the manifest file to extract dependencies
        try:
            tree = ast.parse(content)
            
            # Execute the manifest file to get the dictionary
            local_vars = {}
            exec(content, {}, local_vars)
            
            # Find the manifest dictionary
            manifest_dict = None
            for var_name, var_value in local_vars.items():
                if isinstance(var_value, dict) and 'name' in var_value:
                    manifest_dict = var_value
                    break
            
            if manifest_dict and 'depends' in manifest_dict:
                dependencies = manifest_dict['depends']
                if isinstance(dependencies, (list, tuple)):
                    dependencies = list(dependencies)
                else:
                    dependencies = []
            
        except Exception as e:
            logger.error(f"Error parsing manifest file {manifest_file}: {str(e)}")
            # Fallback: try regex pattern matching
            depends_pattern = r'["\']depends["\']\s*:\s*\[(.*?)\]'
            match = re.search(depends_pattern, content, re.DOTALL)
            if match:
                deps_content = match.group(1)
                # Extract individual dependencies
                dep_pattern = r'["\']([^"\']+)["\']'
                dependencies = re.findall(dep_pattern, deps_content)
    
    except Exception as e:
        logger.error(f"Error reading manifest file {manifest_file}: {str(e)}")
    
    logger.debug(f"Current dependencies in manifest: {dependencies}")
    return dependencies

def _update_manifest_dependencies_safely(manifest_file, dependencies_to_add, logger):
    """
    Update the manifest file by ADDING new dependencies to existing ones.
    This function preserves all existing dependencies and only adds new ones.
    """
    try:
        # Try different encodings to handle various file encodings
        encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252', 'iso-8859-1']
        
        content = None
        used_encoding = None
        
        for encoding in encodings_to_try:
            try:
                with open(manifest_file, 'r', encoding=encoding) as f:
                    content = f.read()
                    used_encoding = encoding
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.error(f"Unexpected error reading {manifest_file} with encoding {encoding}: {e}")
                continue
        
        if content is None:
            logger.error(f"Could not read manifest file {manifest_file} with any encoding")
            return False
        
        # Get current dependencies first by reading the actual file content again
        current_deps = _get_manifest_dependencies(manifest_file, logger)
        logger.info(f"BEFORE UPDATE - Current dependencies: {sorted(current_deps)}")
        
        # Only add dependencies that don't already exist
        new_deps_to_add = []
        for dep in dependencies_to_add:
            if dep not in current_deps:
                new_deps_to_add.append(dep)
                logger.info(f"Will add new dependency: {dep}")
            else:
                logger.info(f"Dependency already exists, skipping: {dep}")
        
        if not new_deps_to_add:
            logger.info(f"All requested dependencies already exist in manifest: {dependencies_to_add}")
            return True
        
        original_content = content
        
        # Find the current dependencies array in the file
        depends_pattern = r'(["\']depends["\']\s*:\s*\[)([^\]]*)\]'
        match = re.search(depends_pattern, content, re.DOTALL)
        
        if not match:
            logger.error(f"Could not find depends pattern in {manifest_file}")
            return False
        
        # Extract the current dependencies string content
        deps_prefix = match.group(1)  # 'depends': [
        deps_content = match.group(2)  # the content between [ and ]
        
        # Parse existing dependencies from the content
        existing_dep_pattern = r'["\']([^"\']+)["\']'
        existing_deps = re.findall(existing_dep_pattern, deps_content)
        
        logger.info(f"Parsed existing dependencies from file: {sorted(existing_deps)}")
        
        # Create final dependencies list by combining existing + new
        final_dependencies = sorted(set(existing_deps + new_deps_to_add))
        
        # Create the new dependencies string
        deps_str = ", ".join([f"'{dep}'" for dep in final_dependencies])
        new_full_pattern = f"{deps_prefix}{deps_str}]"
        
        # Replace only the dependencies array
        updated_content = re.sub(depends_pattern, new_full_pattern, content, flags=re.DOTALL)
        
        if updated_content != original_content:
            # Write back to file
            try:
                with open(manifest_file, 'w', encoding=used_encoding) as f:
                    f.write(updated_content)
                
                logger.info(f"AFTER UPDATE - Dependencies preserved: {sorted(existing_deps)}")
                logger.info(f"AFTER UPDATE - Dependencies added: {sorted(new_deps_to_add)}")
                logger.info(f"AFTER UPDATE - Final dependencies: {sorted(final_dependencies)}")
                
                # Verify the update worked by re-reading the file
                verify_deps = _get_manifest_dependencies(manifest_file, logger)
                if sorted(set(verify_deps)) != sorted(set(final_dependencies)):
                    logger.error(f"Verification failed! Expected: {sorted(final_dependencies)}, Got: {sorted(verify_deps)}")
                    return False
                else:
                    logger.info("Dependency update verified successfully!")
                
                return True
            except Exception as e:
                logger.error(f"Error writing back to {manifest_file}: {e}")
                return False
        else:
            logger.warning(f"No changes were made to {manifest_file}")
            return False
    
    except Exception as e:
        logger.error(f"Error updating manifest file {manifest_file}: {str(e)}")
        return False


def _add_missing_dependencies_from_xml(logger, module_path, module_name, manifest_path, migration_steps, tools):
    """
    Scan XML files for module references and automatically add missing dependencies to manifest.
    
    This function will:
    1. Find all XML files in the module
    2. Extract module references from XML content (like project.menu_project_config)
    3. Check current manifest dependencies  
    4. Add ONLY missing dependencies to the manifest file (preserves ALL existing dependencies)
    5. Log all changes made
    """
    
    logger.info(f"Starting dependency analysis for module: {module_name}")
    
    # Find manifest file
    manifest_file = _find_manifest_file(module_path)
    if not manifest_file:
        logger.warning(f"No manifest file found in module {module_name}")
        return
    
    # Get all XML files
    xml_files = _get_xml_files(module_path)
    if not xml_files:
        logger.info(f"No XML files found in module {module_name}")
        return
    
    logger.info(f"Found {len(xml_files)} XML files to analyze")
    
    # Extract module references from all XML files
    all_module_references = set()
    xml_file_references = {}
    
    for xml_file in xml_files:
        file_references = _extract_module_references_from_xml(xml_file, logger)
        if file_references:
            xml_file_references[xml_file.name] = file_references
            all_module_references.update(file_references)
            logger.info(f"File {xml_file.name} references modules: {sorted(file_references)}")
    
    if not all_module_references:
        logger.info(f"No external module references found in XML files of {module_name}")
        return
    
    logger.info(f"Total unique module references found: {sorted(all_module_references)}")
    
    # Get current dependencies from manifest
    current_dependencies = _get_manifest_dependencies(manifest_file, logger)
    logger.info(f"Current dependencies in manifest (WILL BE PRESERVED): {sorted(current_dependencies)}")
    
    # Find missing dependencies - only add what's not already there
    missing_dependencies = []
    already_present = []
    
    for module_ref in all_module_references:
        # Skip if the referenced module is the same as current module
        if module_ref == module_name:
            logger.debug(f"Ignoring self-reference to current module: {module_ref}")
            continue
            
        if module_ref not in current_dependencies:
            missing_dependencies.append(module_ref)
            logger.info(f"Missing dependency found: {module_ref}")
        else:
            already_present.append(module_ref)
            logger.info(f"Dependency already present: {module_ref}")
    
    if not missing_dependencies:
        logger.info(f"All referenced modules are already in dependencies. No changes needed.")
        logger.info(f"Dependencies will remain: {sorted(current_dependencies)}")
        return
    
    logger.info(f"Dependencies that will be ADDED: {sorted(missing_dependencies)}")
    logger.info(f"Dependencies that will be PRESERVED: {sorted(current_dependencies)}")
    logger.info(f"Expected final dependencies: {sorted(set(current_dependencies + missing_dependencies))}")
    
    # Update manifest file with ONLY the missing dependencies
    if _update_manifest_dependencies_safely(manifest_file, missing_dependencies, logger):
        logger.info(f"Successfully updated manifest dependencies in {manifest_file}")
        
        # Log detailed information about which files reference which modules
        logger.info("Detailed module reference mapping:")
        for xml_file, references in xml_file_references.items():
            for ref in references:
                if ref in missing_dependencies:
                    logger.info(f"  {xml_file} -> {ref} (ADDED to manifest)")
                elif ref in current_dependencies:
                    logger.info(f"  {xml_file} -> {ref} (already in manifest - PRESERVED)")
    else:
        logger.error(f"Failed to update manifest dependencies in {manifest_file}")

class MigrationScript(BaseMigrationScript):

    _GLOBAL_FUNCTIONS = [_check_open_form, _reformat_read_group, replace_attrs_expressions,_update_manifest_version_for_v17,_replace_config_settings_xpath,_comment_assets_js_xml_files]
