
from odoo_module_upgrade.base_migration_script import BaseMigrationScript
import re


def replace_tree_with_list_in_views(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    files_to_process = tools.get_files(module_path, (".xml", ".js", ".py"))

    reg_tree_to_list_xml_mode = re.compile(
        r"""(<field[^>]* name=["'](view_mode|name|binding_view_types)["'][^>]*>([^<>]+[,.])?\s*)tree(\s*([,.][^<>]+)?</field>)"""
    )
    reg_tree_to_list_tag = re.compile(r"([<,/])tree([ \n\r,>/])")
    reg_tree_to_list_xpath = re.compile(
        r"""(<xpath[^>]* expr=['"])([^<>]*/)?tree(/|[\['"])"""
    )
    reg_tree_to_list_ref = re.compile(r"tree_view_ref")
    reg_tree_to_list_mode = re.compile(r"""(mode=['"][^'"]*)tree([^'"]*['"])""")
    reg_tree_to_list_view_mode = re.compile(
        r"""(['"]view_mode['"][^'":=]*[:=].*['"]([^'"]+,)?\s*)tree(\s*(,[^'"]+)?['"])"""
    )
    reg_tree_to_list_view = re.compile(
        r"""(['"]views['"][^'":]*[:=].*['"])tree(['"])"""
    )
    reg_tree_to_list_string = re.compile(r"""([ '">)])tree( [vV]iews?[ '"<.)])""")
    reg_tree_to_list_String = re.compile(r"""([ '">)])Tree( [vV]iews?[ '"<.)])""")
    reg_tree_to_list_env_ref = re.compile(r"""(self\.env\.ref\(.*['"])tree(['"])""")

    for file in files_to_process:
        try:
            content = tools._read_content(file)
            content = content.replace(" tree view ", " list view ")
            content = reg_tree_to_list_xml_mode.sub(r"\1list\4", content)
            content = reg_tree_to_list_tag.sub(r"\1list\2", content)
            content = reg_tree_to_list_xpath.sub(r"\1\2list\3", content)
            content = reg_tree_to_list_ref.sub("list_view_ref", content)
            content = reg_tree_to_list_mode.sub(r"\1list\2", content)
            content = reg_tree_to_list_view_mode.sub(r"\1list\3", content)
            content = reg_tree_to_list_view.sub(r"\1list\2", content)
            content = reg_tree_to_list_string.sub(r"\1list\2", content)
            content = reg_tree_to_list_String.sub(r"\1List\2", content)
            content = reg_tree_to_list_env_ref.sub(r"\1list\2", content)

            tools._write_content(file, content)

        except Exception as e:
            logger.error(f"Error processing file {file}: {str(e)}")


def replace_chatter_blocks(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    files_to_process = tools.get_files(module_path, (".xml",))

    reg_chatter_block = r"""<div class=["']oe_chatter["'](?![^>]*position=["'][^"']+["'])[^>]*>[\s\S]*?</div>"""
    reg_xpath_chatter = r"""//div\[hasclass\(['"]oe_chatter['"]\)\]"""
    reg_chatter_with_position_self_closing = (
        r"""<div class=["']oe_chatter["']\s*(position=["'][^"']+["'])\s*/>"""
    )

    replacement_div = "<chatter/>"
    replacement_xpath = "//chatter"

    def replace_chatter_self_closing(match):
        position = match.group(1)
        return f"<chatter {position}/>"

    replaces = {
        reg_chatter_block: replacement_div,
        reg_xpath_chatter: replacement_xpath,
        reg_chatter_with_position_self_closing: replace_chatter_self_closing,
    }

    for file in files_to_process:
        try:
            tools._replace_in_file(
                file, replaces, log_message=f"Updated chatter blocks in file: {file}"
            )
        except Exception as e:
            logger.error(f"Error processing file {file}: {str(e)}")


def replace_deprecated_kanban_box_card_menu(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    files_to_process = tools.get_files(module_path, (".xml", ".js", ".py"))
    replaces = {
        "kanban-card": "card",
        "kanban-box": "card",
        "kanban-menu": "menu",
    }
    for file in files_to_process:
        try:
            tools._replace_in_file(
                file,
                replaces,
                log_message=f"""Replace kanban-card and kanban-box with card, also change kanban-menu with menu" in file: {file}""",
            )
        except Exception as e:
            logger.error(f"Error processing file {file}: {str(e)}")


def replace_user_has_groups(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    files_to_process = tools.get_files(module_path, (".py",))
    replaces = {
        r"self\.user_has_groups\(\s*(['\"])([\w\.]+)\1\s*\)": r"self.env.user.has_group(\1\2\1)",
        r"self\.user_has_groups\(\s*(['\"])([^'\"]*[,!][^'\"]*?)\1\s*\)": r"self.env.user.has_groups(\1\2\1)",
    }

    for file in files_to_process:
        try:
            tools._replace_in_file(file, replaces)
        except Exception as e:
            logger.error(f"Error processing file {file}: {str(e)}")


def replace_unaccent_parameter(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    files_to_process = tools.get_files(module_path, (".py",))
    replaces = {
        # Handle multiline with unaccent=False or unaccent=True
        r"(?s)fields\.(Char|Text|Html|Properties)\(\s*unaccent\s*=\s*(False|True)\s*,?\s*\)": r"fields.\1()",
        # Handle when unaccent=False or unaccent=True is the first parameter
        r"(?s)fields\.(Char|Text|Html|Properties)\(\s*unaccent\s*=\s*(False|True)\s*,\s*([^)]+?)\)": r"fields.\1(\3)",
        # Handle when unaccent=False or unaccent=True is between other parameters
        r"(?s)fields\.(Char|Text|Html|Properties)\(([^)]+?),\s*unaccent\s*=\s*(False|True)\s*,\s*([^)]+?)\)": r"fields.\1(\2, \4)",
        # Handle when unaccent=False or unaccent=True is the last parameter
        r"(?s)fields\.(Char|Text|Html|Properties)\(([^)]+?),\s*unaccent\s*=\s*(False|True)\s*\)": r"fields.\1(\2)",
    }

    for file in files_to_process:
        try:
            tools._replace_in_file(
                file,
                replaces,
                log_message=f"[18.0] Removed deprecated unaccent=False parameter in file: {file}",
            )
        except Exception as e:
            logger.error(f"Error processing file {file}: {str(e)}")


def replace_ustr(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    files_to_process = tools.get_files(module_path, (".py",))
    replaces = {
        r"from\s+odoo\.tools\s+import\s+ustr\s*\n": "",
        r"from\s+odoo\.tools\.misc\s+import\s+ustr\s*\n": "",
        r"from\s+odoo\.tools\s+import\s+([^,\n]*,\s*)?ustr,\s*([^,\n]*)": r"from odoo.tools import \1\2",
        r"from\s+odoo\.tools\.misc\s+import\s+([^,\n]*,\s*)?ustr,\s*([^,\n]*)": r"from odoo.tools.misc import \1\2",
        r",\s*ustr(\s*,)?": r"\1",
        r"tools\.ustr\(([^)]+)\)": r"\1",
        r"misc\.ustr\(([^)]+)\)": r"\1",
        r"=\s*ustr\(([^)]+)\)": r"= \1",
    }
    for file in files_to_process:
        try:
            tools._replace_in_file(
                file, replaces, log_message=f"Deprecate ustr in: {file}"
            )
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

def _update_manifest_version_for_v18(logger, module_path, module_name, manifest_path, migration_steps, tools):
    """Update manifest version to be compatible with Odoo 18."""
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
                if version_parts[0] != '18' or version_parts[1] != '0':
                    if len(version_parts) >= 3:
                        new_version = f"18.0.{version_parts[2]}"
                        if len(version_parts) > 3:
                            new_version += f".{'.'.join(version_parts[3:])}"
                    else:
                        new_version = "18.0.1.0.0"
                else:
                    new_version = original_version
            else:
                new_version = "18.0.1.0.0"
            
            if original_version == new_version:
                logger.info(f"Manifest version '{original_version}' already compatible with Odoo 18 in {manifest_file}")
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

def replace_xml_field_type_tree(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    """
    Replace <field name="type">tree</field> with <field name="type">list</field>
    in XML files as this syntax is not supported in Odoo 18 anymore.
    """
    files_to_process = tools.get_files(module_path, (".xml",))
    
    # Pattern to match <field name="type">tree</field> with optional whitespace
    reg_field_type_tree = re.compile(
        r'(<field\s+name=["\']\s*type\s*["\']\s*>\s*)tree(\s*</field>)',
        re.IGNORECASE
    )
    
    files_modified = 0
    total_replacements = 0
    
    for file in files_to_process:
        try:
            logger.debug(f"Processing XML file for field type tree replacement: {file}")
            
            content = tools._read_content(file)
            original_content = content
            
            # Count matches before replacement for logging
            matches = reg_field_type_tree.findall(content)
            file_replacements = len(matches)
            
            if file_replacements > 0:
                # Replace tree with list in field type definitions
                content = reg_field_type_tree.sub(r'\1list\2', content)
                
                # Write the modified content back to file
                tools._write_content(file, content)
                
                files_modified += 1
                total_replacements += file_replacements
                
                logger.info(
                    f"Replaced {file_replacements} '<field name=\"type\">tree</field>' "
                    f"occurrences with 'list' in file: {file}"
                )
            else:
                logger.debug(f"No '<field name=\"type\">tree</field>' patterns found in: {file}")
                
        except Exception as e:
            logger.error(f"Error processing XML file {file} for field type replacement: {str(e)}")
    
    if total_replacements > 0:
        logger.info(
            f"[Odoo 18 Migration] Successfully replaced {total_replacements} "
            f"'<field name=\"type\">tree</field>' patterns across {files_modified} XML files"
        )
    else:
        logger.info("[Odoo 18 Migration] No '<field name=\"type\">tree</field>' patterns found to replace")

def remove_deprecated_ir_cron_fields(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    """
    Remove deprecated fields from ir.cron records in XML files as these fields 
    are not supported in Odoo 18 anymore:
    - <field name="numbercall">-1</field> - infinite repetitions is now default
    - <field name="doall" eval="False|True"/> - this field is deprecated regardless of value
    
    Handles all combinations of single/double quotes, attribute orders, and self-closing tags.
    """
    files_to_process = tools.get_files(module_path, (".xml",))
    
    # Enhanced patterns to match numbercall fields with any quote combination and whitespace
    # reg_numbercall_field = re.compile(
    #     r'<field\s+name=(["\'])numbercall\1\s*>-1</field>\s*',
    #     re.IGNORECASE
    # )
    reg_numbercall_field = re.compile(
        r'<field\s+name=(["\'])numbercall\1\s*>-?\d+</field>\s*',
        re.IGNORECASE
    )
    
    # Pattern to match numbercall field with surrounding whitespace for better cleanup
    # reg_numbercall_field_with_whitespace = re.compile(
    #     r'\s*<field\s+name=(["\'])numbercall\1\s*>-1</field>\s*(?=\n)',
    #     re.IGNORECASE
    # )
    reg_numbercall_field_with_whitespace = re.compile(
        r'\s*<field\s+name=(["\'])numbercall\1\s*>-?\d+</field>\s*(?=\n)',
        re.IGNORECASE
    )
    
    # Enhanced patterns to match doall fields - covers all attribute orders and quote combinations
    # Pattern 1: name first, eval second, self-closing - <field name="doall" eval="False|True"/>
    reg_doall_field_name_first = re.compile(
        r'<field\s+name=(["\'])doall\1\s+eval=(["\'])(?:False|True)\2\s*/>\s*',
        re.IGNORECASE
    )
    
    # Pattern 2: eval first, name second, self-closing - <field eval="False|True" name="doall"/>
    reg_doall_field_eval_first = re.compile(
        r'<field\s+eval=(["\'])(?:False|True)\1\s+name=(["\'])doall\2\s*/>\s*',
        re.IGNORECASE
    )
    
    # Pattern 3: non-self-closing with name only - <field name="doall">False|True</field>
    reg_doall_field_non_closing = re.compile(
        r'<field\s+name=(["\'])doall\1\s*>(?:False|True)</field>\s*',
        re.IGNORECASE
    )
    
    # Whitespace cleanup patterns for doall fields
    reg_doall_field_name_first_with_whitespace = re.compile(
        r'\s*<field\s+name=(["\'])doall\1\s+eval=(["\'])(?:False|True)\2\s*/>\s*(?=\n)',
        re.IGNORECASE
    )
    
    reg_doall_field_eval_first_with_whitespace = re.compile(
        r'\s*<field\s+eval=(["\'])(?:False|True)\1\s+name=(["\'])doall\2\s*/>\s*(?=\n)',
        re.IGNORECASE
    )
    
    reg_doall_field_non_closing_with_whitespace = re.compile(
        r'\s*<field\s+name=(["\'])doall\1\s*>(?:False|True)</field>\s*(?=\n)',
        re.IGNORECASE
    )
    
    files_modified = 0
    total_numbercall_removals = 0
    total_doall_removals = 0
    
    for file in files_to_process:
        try:
            logger.debug(f"Processing XML file for ir.cron deprecated fields removal: {file}")
            
            content = tools._read_content(file)
            original_content = content
            
            # Check if file contains ir.cron model references to avoid unnecessary processing
            if 'ir.cron' not in content and 'model="ir.cron"' not in content:
                logger.debug(f"No ir.cron references found in: {file}")
                continue
            
            # Count matches before removal for logging
            numbercall_matches = reg_numbercall_field.findall(content)
            
            # Count all doall field variations
            doall_matches_name_first = reg_doall_field_name_first.findall(content)
            doall_matches_eval_first = reg_doall_field_eval_first.findall(content)
            doall_matches_non_closing = reg_doall_field_non_closing.findall(content)
            
            file_numbercall_removals = len(numbercall_matches)
            file_doall_removals = len(doall_matches_name_first) + len(doall_matches_eval_first) + len(doall_matches_non_closing)
            
            content_modified = False
            
            # Remove numbercall fields
            if file_numbercall_removals > 0:
                # First try to remove with whitespace cleanup
                content = reg_numbercall_field_with_whitespace.sub('', content)
                # Then remove any remaining instances
                content = reg_numbercall_field.sub('', content)
                content_modified = True
                total_numbercall_removals += file_numbercall_removals
                
                logger.info(
                    f"Removed {file_numbercall_removals} deprecated '<field name=\"numbercall\">-1</field>' "
                    f"from ir.cron records in file: {file}"
                )
            
            # Remove doall fields - all variations
            if file_doall_removals > 0:
                # Remove doall fields with name first (with whitespace cleanup)
                content = reg_doall_field_name_first_with_whitespace.sub('', content)
                content = reg_doall_field_name_first.sub('', content)
                
                # Remove doall fields with eval first (with whitespace cleanup) 
                content = reg_doall_field_eval_first_with_whitespace.sub('', content)
                content = reg_doall_field_eval_first.sub('', content)
                
                # Remove non-self-closing doall fields (with whitespace cleanup)
                content = reg_doall_field_non_closing_with_whitespace.sub('', content)
                content = reg_doall_field_non_closing.sub('', content)
                
                content_modified = True
                total_doall_removals += file_doall_removals
                
                logger.info(
                    f"Removed {file_doall_removals} deprecated '<field name=\"doall\">' "
                    f"from ir.cron records in file: {file}"
                )
            
            # Write the modified content back to file if any changes were made
            if content_modified:
                tools._write_content(file, content)
                files_modified += 1
            else:
                logger.debug(f"No deprecated ir.cron fields found in: {file}")
                
        except Exception as e:
            logger.error(f"Error processing XML file {file} for ir.cron deprecated fields removal: {str(e)}")
    
    # Summary logging
    if total_numbercall_removals > 0 or total_doall_removals > 0:
        summary_msg = f"[Odoo 18 Migration] Successfully removed deprecated ir.cron fields across {files_modified} XML files:"
        if total_numbercall_removals > 0:
            summary_msg += f" {total_numbercall_removals} 'numbercall=-1' fields"
        if total_doall_removals > 0:
            if total_numbercall_removals > 0:
                summary_msg += " and"
            summary_msg += f" {total_doall_removals} 'doall' fields (regardless of value)"
        logger.info(summary_msg)
    else:
        logger.info("[Odoo 18 Migration] No deprecated ir.cron fields found to remove")

def replace_active_id_with_parent_id(
    logger, module_path, module_name, manifest_path, migration_steps, tools
):
    """
    Replace 'active_id' with 'parent.id' in field definitions within form views.
    
    This handles field context attributes where active_id is used, which is common
    in one2many and many2many fields that need to reference the parent record.
    
    Examples of patterns that will be replaced:
    - 'default_version_id': active_id  -> 'default_version_id': parent.id
    - "default_version_id": active_id  -> "default_version_id": parent.id
    - context="{'default_version_id': active_id, 'other': value}" 
    - context="{'other': value, 'default_version_id': active_id}"
    - context='{"default_version_id": active_id, "other": value}'
    """
    files_to_process = tools.get_files(module_path, (".xml",))
    
    # Comprehensive pattern to match active_id in any context within field tags
    # This pattern handles:
    # 1. Any quote combination for context attribute (single or double)
    # 2. Any quote combination for keys inside context (single or double) 
    # 3. Any position of active_id within the context
    # 4. Optional whitespace around colons and commas
    # 5. Both comma-separated and end-of-context positions
    
    # Pattern matches: ['"]key['"]:\s*active_id followed by comma, space, or end of context
    reg_active_id_in_context = re.compile(
        r"""(['"][^'"]*['"]:\s*)active_id(\s*[,}\s])""",
        re.IGNORECASE
    )
    
    files_modified = 0
    total_replacements = 0
    
    for file in files_to_process:
        try:
            logger.debug(f"Processing XML file for active_id replacement: {file}")
            
            content = tools._read_content(file)
            original_content = content
            
            # Check if file contains field definitions with context to avoid unnecessary processing
            if 'context=' not in content or 'active_id' not in content:
                logger.debug(f"No context with active_id found in: {file}")
                continue
            
            # Count active_id occurrences before replacement for logging
            before_count = len(re.findall(r'\bactive_id\b', content, re.IGNORECASE))
            
            if before_count > 0:
                # Replace all active_id occurrences in context attributes
                # This single pattern handles all variations:
                # - Different quote types for context attribute
                # - Different quote types for keys inside context  
                # - Different positions within context
                # - With or without spaces around colons
                content = reg_active_id_in_context.sub(r'\1parent.id\2', content)
                
                # Count remaining active_id occurrences after replacement
                after_count = len(re.findall(r'\bactive_id\b', content, re.IGNORECASE))
                file_replacements = before_count - after_count
                
                # Write the modified content back to file if any changes were made
                if content != original_content and file_replacements > 0:
                    tools._write_content(file, content)
                    files_modified += 1
                    total_replacements += file_replacements
                    
                    logger.info(
                        f"Replaced {file_replacements} 'active_id' occurrences with 'parent.id' "
                        f"in context attributes in file: {file}"
                    )
                else:
                    logger.debug(f"No changes made to file: {file}")
            else:
                logger.debug(f"No 'active_id' patterns found in: {file}")
                
        except Exception as e:
            logger.error(f"Error processing XML file {file} for active_id replacement: {str(e)}")
    
    # Summary logging
    if total_replacements > 0:
        logger.info(
            f"[Odoo Migration] Successfully replaced {total_replacements} "
            f"'active_id' occurrences with 'parent.id' across {files_modified} XML files"
        )
    else:
        logger.info("[Odoo Migration] No 'active_id' patterns found to replace in field contexts")

class MigrationScript(BaseMigrationScript):
    _GLOBAL_FUNCTIONS = [
        replace_unaccent_parameter,
        replace_deprecated_kanban_box_card_menu,
        replace_tree_with_list_in_views,
        replace_chatter_blocks,
        replace_user_has_groups,
        replace_ustr,
        _update_manifest_version_for_v18,
        replace_xml_field_type_tree,
        remove_deprecated_ir_cron_fields,
        replace_active_id_with_parent_id
    ]
