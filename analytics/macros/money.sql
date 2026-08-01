{% macro normalized_amount_text(column_name) %}
trim(regexp_replace({{ column_name }}, '^(AED|PKR)\s*', ''))
{% endmacro %}

{% macro amount_is_integer(column_name) %}
regexp_full_match({{ normalized_amount_text(column_name) }}, '[+-]?[0-9]+')
{% endmacro %}

{% macro amount_minor(column_name) %}
abs(cast({{ normalized_amount_text(column_name) }} as bigint))
{% endmacro %}

{% macro direction(column_name) %}
case when cast({{ normalized_amount_text(column_name) }} as bigint) < 0 then 'debit' else 'credit' end
{% endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
{{ custom_schema_name | trim if custom_schema_name is not none else target.schema }}
{%- endmacro %}
