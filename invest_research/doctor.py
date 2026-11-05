"""Read-only discovery; never executes vendor tools, reads credentials or tests access."""
import importlib.util
from pathlib import Path
import re
import shutil
import sys


def inventory(skill_dirs=()):
    binaries={name:bool(shutil.which(name)) for name in ('westock','node','npx','westock-data-skillhub')}
    candidates=[Path.home()/'.workbuddy'/'skills'/'westock-data',
                Path.home()/'.config'/'opencode'/'skills'/'westock-data',
                *(Path(p) for p in skill_dirs)]
    skills=[]
    seen=set()
    for candidate in candidates:
        path=candidate/'SKILL.md' if candidate.is_dir() else candidate
        if path in seen:
            continue
        seen.add(path)
        if not path.is_file():
            continue
        try:
            text=path.read_text(encoding='utf-8-sig')
        except (OSError,UnicodeError):
            skills.append({'skill':'westock-data','readable':False,'publisher':'not_verified'})
            continue
        versions=sorted(set(re.findall(r'westock-data-skillhub@([0-9]+\.[0-9]+\.[0-9]+)',text)))
        skills.append({'skill':'westock-data','readable':True,'npm_package_referenced':bool(versions),
                       'referenced_npm_versions':versions,'publisher':'not_verified'})
    return {'python_required':'3.10+','python_version':sys.version.split()[0],
            'westock_cli_installed':binaries['westock'], 'binaries':binaries,
            'skills_discovered':skills,
            'tool_discovered':binaries['westock'] or binaries['westock-data-skillhub'] or bool(skills),
            'mcp_sdk_installed':importlib.util.find_spec('mcp') is not None,
            'supplier_access':'not_tested', 'network':'not_tested', 'publisher':'not_verified',
            'scope':'PATH and known/explicit skill paths only; no MCP configuration or credential inspection',
            'note':'工具发现不等于已授权；CLI缺失不代表宿主MCP不可用，Python MCP SDK缺失也不代表未配置MCP。'}
