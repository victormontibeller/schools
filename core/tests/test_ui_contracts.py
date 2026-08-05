"""Testes do shell canônico e do catálogo de UI."""

from core.ui_catalog import LIST_PAGE_CATALOG
from core.ui_contract_checker import _check_tabs_contract, check_ui_contracts


def test_ui_contracts_have_no_violations() -> None:
    assert check_ui_contracts() == []


def test_schedule_classes_list_has_canonical_catalog_contract() -> None:
    definition = LIST_PAGE_CATALOG["schedule_classes_list"]

    assert definition.search_target == "#schedule-classes-table"
    assert definition.create_url is None


def test_tabs_contract_accepts_canonical_component_and_duralux_reference() -> None:
    direct_tabs = '<nav class="nav nav-tabs"><a role="tab" data-bs-toggle="tab"></a></nav>'

    assert _check_tabs_contract("templates/partials/list_tabs.html", direct_tabs) == []
    assert _check_tabs_contract("design_system/refs/duralux/index.html", direct_tabs) == []


def test_tabs_contract_accepts_similar_non_tab_attributes() -> None:
    source = (
        "<div tabindex=0 role=tablist data-role=tab>"
        "<section role=TABPANEL><button data-bs-toggle=dropdown></button></section>"
        "<div class=table-tab-pane></div>"
        "</div>"
    )

    assert _check_tabs_contract("example/templates/example/detail.html", source) == []


def test_tabs_contract_rejects_direct_tab_implementations() -> None:
    sources = (
        ("nav-tabs", '<nav class="nav nav-tabs"></nav>'),
        ("nav-tabs", "<nav CLASS=NAV-TABS></nav>"),
        ("nav-pills", "<nav class='nav nav-pills'></nav>"),
        ("nav-pills", "<nav CLASS=NAV-PILLS></nav>"),
        ("tab-pane", '<div class="tab-pane"></div>'),
        ("tab-pane", "<div class=TAB-PANE></div>"),
        ("role=tab", '<button role="tab"></button>'),
        ("role=tab", "<button role=TaB></button>"),
        ("data-bs-toggle=tab|pill", '<button data-bs-toggle="tab"></button>'),
        ("data-bs-toggle=tab|pill", "<button DATA-BS-TOGGLE=PILL></button>"),
    )

    for expected_token, source in sources:
        assert _check_tabs_contract("example/templates/example/detail.html", source) == [
            "Abas fora do componente canônico em example/templates/example/detail.html: "
            f"{expected_token}"
        ]
