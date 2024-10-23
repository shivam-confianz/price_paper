###################################################################################
#
#    Copyright (c) 2017-2019 MuK IT GmbH.
#
#    This file is part of MuK Utils
#    (see https://mukit.at).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU Lesser General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#
###################################################################################

from odoo import api, fields, models


class Groups(models.AbstractModel):

    _name = "muk_utils.mixins.groups"
    _description = "Group Mixin"

    _parent_store = True
    _parent_name = "parent_group"

    # ----------------------------------------------------------
    # Database
    # ----------------------------------------------------------

    name = fields.Char(string="Group Name", required=True, translate=True)

    parent_path = fields.Char(string="Parent Path", index=True)

    count_users = fields.Integer(compute="_compute_users", string="Users", store=True)

    parent_group = fields.Many2one(_module=lambda self: self._module,comodel_name='muk_utils.mixins.groups',string="Parent Group",
                                   ondelete="cascade",
                                   auto_join=True,
                                   index=True,
                                   automatic=True,
                                   )

    child_groups = fields.One2many(_module=lambda self: self._module,comodel_name='muk_utils.mixins.groups',inverse_name="parent_group",
        string="Child Groups",
        automatic=True,
    )

    groups = fields.Many2many(_module=lambda self: self._module,comodel_name="res.groups",relation="muk_utils_mixins_groups_groups_rel",
        column1="gid",
        column2="rid",
        string="Groups",
        automatic=True,
    )

    explicit_users = fields.Many2many(_module=lambda self:self._module,comodel_name="res.users",relation="muk_utils_mixins_groups_explicit_users_rel",
        column1="gid",column2="uid",
        string="Explicit Users",
        automatic=True,
    )

    users = fields.Many2many(_module=lambda self:self._module, comodel_name="res.users",relation="muk_utils_mixins_groups_users_rel",
        column1="gid",
        column2="uid",
        string="Group Users",
        compute="_compute_users",
        store=True,
        automatic=True,
    )

    _sql_constraints = [
        ("name_uniq", "unique (name)", "The name of the group must be unique!")
    ]

    # ----------------------------------------------------------
    # Functions
    # ----------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        res = super(Groups, self).default_get(fields_list)
        if not self.env.context.get("groups_no_autojoin"):
            if "explicit_users" in res and res["explicit_users"]:
                res["explicit_users"] = res["explicit_users"] + [self.env.uid]
            else:
                res["explicit_users"] = [self.env.uid]
        return res

    # ----------------------------------------------------------
    # Read, View
    # ----------------------------------------------------------

    @api.depends(
        "parent_group", "parent_group.users", "groups", "groups.users", "explicit_users"
    )
    def _compute_users(self):
        for record in self:
            users = record.mapped("groups.users")
            users |= record.mapped("explicit_users")
            users |= record.mapped("parent_group.users")
            record.update({"users": users, "count_users": len(users)})