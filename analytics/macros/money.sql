{% macro normalized_amount_text(column_name) %}
trim(regexp_replace({{ column_name }}, '^(AED|PKR)\s*', ''))
{% endmacro %}

{% macro parsed_amount(column_name) %}
try_cast({{ normalized_amount_text(column_name) }} as bigint)
{% endmacro %}

{% macro amount_is_integer(column_name, parsed_column_name) %}
regexp_full_match({{ normalized_amount_text(column_name) }}, '[+-]?[0-9]+')
and {{ parsed_column_name }} is not null
and {{ parsed_column_name }} <> try_cast('-9223372036854775808' as bigint)
{% endmacro %}

{% macro amount_minor(parsed_column_name) %}
abs({{ parsed_column_name }})
{% endmacro %}

{% macro direction(parsed_column_name) %}
case when {{ parsed_column_name }} < 0 then 'debit' else 'credit' end
{% endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
{{ custom_schema_name | trim if custom_schema_name is not none else target.schema }}
{%- endmacro %}
