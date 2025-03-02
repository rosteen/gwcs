# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
This module contains a mixin class which exposes the WCS API defined
in astropy APE 14 (https://doi.org/10.5281/zenodo.1188875).

"""

import astropy.units as u
from astropy.modeling import separable
from astropy.wcs.wcsapi import BaseLowLevelWCS, HighLevelWCSMixin

from gwcs import utils

__all__ = ["GWCSAPIMixin"]


class GWCSAPIMixin(BaseLowLevelWCS, HighLevelWCSMixin):
    """
    A mix-in class that is intended to be inherited by the
    :class:`~gwcs.wcs.WCS` class and provides the low- and high-level
    WCS API described in the astropy APE 14
    (https://doi.org/10.5281/zenodo.1188875).
    """

    # Low Level APE 14 API
    @property
    def pixel_n_dim(self):
        """
        The number of axes in the pixel coordinate system.
        """
        if self.input_frame is None:
            return self.forward_transform.n_inputs
        return self.input_frame.naxes

    @property
    def world_n_dim(self):
        """
        The number of axes in the world coordinate system.
        """
        if self.output_frame is None:
            return self.forward_transform.n_outputs
        return self.output_frame.naxes

    @property
    def world_axis_physical_types(self):
        """
        An iterable of strings describing the physical type for each world axis.
        These should be names from the VO UCD1+ controlled Vocabulary
        (http://www.ivoa.net/documents/latest/UCDlist.html). If no matching UCD
        type exists, this can instead be ``"custom:xxx"``, where ``xxx`` is an
        arbitrary string.  Alternatively, if the physical type is
        unknown/undefined, an element can be `None`.
        """
        return self.output_frame.axis_physical_types

    @property
    def world_axis_units(self):
        """
        An iterable of strings given the units of the world coordinates for each
        axis.
        The strings should follow the `IVOA VOUnit standard
        <http://ivoa.net/documents/VOUnits/>`_ (though as noted in the VOUnit
        specification document, units that do not follow this standard are still
        allowed, but just not recommended).
        """
        return tuple(unit.to_string(format="vounit") for unit in self.output_frame.unit)

    def _remove_quantity_output(self, result, frame):
        if self.forward_transform.uses_quantity:
            if frame.naxes == 1:
                result = [result]

            result = tuple(
                r.to_value(unit) if isinstance(r, u.Quantity) else r
                for r, unit in zip(result, frame.unit, strict=False)
            )

        # If we only have one output axes, we shouldn't return a tuple.
        if self.output_frame.naxes == 1 and isinstance(result, tuple):
            return result[0]
        return result

    def pixel_to_world_values(self, *pixel_arrays):
        """
        Convert pixel coordinates to world coordinates.

        This method takes ``pixel_n_dim`` scalars or arrays as input, and pixel
        coordinates should be zero-based. Returns ``world_n_dim`` scalars or
        arrays in units given by ``world_axis_units``. Note that pixel
        coordinates are assumed to be 0 at the center of the first pixel in each
        dimension. If a pixel is in a region where the WCS is not defined, NaN
        can be returned. The coordinates should be specified in the ``(x, y)``
        order, where for an image, ``x`` is the horizontal coordinate and ``y``
        is the vertical coordinate.
        """
        result = self._call_forward(*pixel_arrays)

        return self._remove_quantity_output(result, self.output_frame)

    def array_index_to_world_values(self, *index_arrays):
        """
        Convert array indices to world coordinates.
        This is the same as `~astropy.wcs.wcsapi.BaseLowLevelWCS.pixel_to_world_values`
        except that the indices should be given in ``(i, j)`` order, where for an image
        ``i`` is the row and ``j`` is the column (i.e. the opposite order to
        `~astropy.wcs.wcsapi.BaseLowLevelWCS.pixel_to_world_values`).
        """
        pixel_arrays = index_arrays[::-1]
        return self.pixel_to_world_values(*pixel_arrays)

    def world_to_pixel_values(self, *world_arrays):
        """
        Convert world coordinates to pixel coordinates.

        This method takes ``world_n_dim`` scalars or arrays as input in units
        given by ``world_axis_units``. Returns ``pixel_n_dim`` scalars or
        arrays. Note that pixel coordinates are assumed to be 0 at the center of
        the first pixel in each dimension. If a world coordinate does not have a
        matching pixel coordinate, NaN can be returned.  The coordinates should
        be returned in the ``(x, y)`` order, where for an image, ``x`` is the
        horizontal coordinate and ``y`` is the vertical coordinate.
        """
        result = self._call_backward(*world_arrays)

        return self._remove_quantity_output(result, self.input_frame)

    def world_to_array_index_values(self, *world_arrays):
        """
        Convert world coordinates to array indices.
        This is the same as `~astropy.wcs.wcsapi.BaseLowLevelWCS.world_to_pixel_values`
        except that the indices should be returned in ``(i, j)`` order, where for an
        image ``i`` is the row and ``j`` is the column (i.e. the opposite order to
        `~astropy.wcs.wcsapi.BaseLowLevelWCS.pixel_to_world_values`). The indices should
        be returned as rounded integers.
        """
        results = self.world_to_pixel_values(*world_arrays)
        results = (results,) if self.pixel_n_dim == 1 else results[::-1]

        results = tuple(utils._toindex(result) for result in results)
        return results[0] if self.pixel_n_dim == 1 else results

    @property
    def array_shape(self):
        """
        The shape of the data that the WCS applies to as a tuple of
        length `~astropy.wcs.wcsapi.BaseLowLevelWCS.pixel_n_dim`.
        If the WCS is valid in the context of a dataset with a particular
        shape, then this property can be used to store the shape of the
        data. This can be used for example if implementing slicing of WCS
        objects. This is an optional property, and it should return `None`
        if a shape is not known or relevant.
        The shape should be given in ``(row, column)`` order (the convention
        for arrays in Python).
        """
        if self._pixel_shape is None:
            return None
        return self._pixel_shape[::-1]

    @array_shape.setter
    def array_shape(self, value):
        if value is None:
            self._pixel_shape = None
        else:
            self._pixel_shape = value[::-1]

    @property
    def pixel_bounds(self):
        """
        The bounds (in pixel coordinates) inside which the WCS is defined,
        as a list with `~astropy.wcs.wcsapi.BaseLowLevelWCS.pixel_n_dim`
        ``(min, max)`` tuples.  The bounds should be given in
        ``[(xmin, xmax), (ymin, ymax)]`` order. WCS solutions are sometimes
        only guaranteed to be accurate within a certain range of pixel values,
        for example when defining a WCS that includes fitted distortions. This
        is an optional property, and it should return `None` if a shape is not
        known or relevant.
        """
        bounding_box = self.bounding_box
        if bounding_box is None:
            return bounding_box

        if self.pixel_n_dim == 1 and len(bounding_box) == 2:
            bounding_box = (bounding_box,)

        # Iterate over the bounding box and convert from quantity if required.
        bounding_box = list(bounding_box)
        for i, bb_axes in enumerate(bounding_box):
            bb = [lim.value if isinstance(lim, u.Quantity) else lim for lim in bb_axes]

            bounding_box[i] = tuple(bb)

        return tuple(bounding_box)

    @property
    def pixel_shape(self):
        """
        The shape of the data that the WCS applies to as a tuple of length
        ``pixel_n_dim`` in ``(x, y)`` order (where for an image, ``x`` is
        the horizontal coordinate and ``y`` is the vertical coordinate)
        (optional).

        If the WCS is valid in the context of a dataset with a particular
        shape, then this property can be used to store the shape of the
        data. This can be used for example if implementing slicing of WCS
        objects. This is an optional property, and it should return `None`
        if a shape is neither known nor relevant.
        """
        return self._pixel_shape

    @pixel_shape.setter
    def pixel_shape(self, value):
        if value is None:
            self._pixel_shape = None
            return
        wcs_naxes = self.input_frame.naxes
        if len(value) != wcs_naxes:
            msg = (
                "The number of data axes, "
                f"{wcs_naxes}, does not equal the "
                f"shape {len(value)}."
            )
            raise ValueError(msg)

        self._pixel_shape = tuple(value)

    @property
    def axis_correlation_matrix(self):
        """
        Returns an (`~astropy.wcs.wcsapi.BaseLowLevelWCS.world_n_dim`,
        `~astropy.wcs.wcsapi.BaseLowLevelWCS.pixel_n_dim`) matrix that indicates
        using booleans whether a given world coordinate depends on a given pixel
        coordinate.  This defaults to a matrix where all elements are `True` in
        the absence of any further information. For completely independent axes,
        the diagonal would be `True` and all other entries `False`.
        """
        return separable.separability_matrix(self.forward_transform)

    @property
    def serialized_classes(self):
        """
        Indicates whether Python objects are given in serialized form or as
        actual Python objects.
        """
        return False

    @property
    def world_axis_object_classes(self):
        return self.output_frame.world_axis_object_classes

    @property
    def world_axis_object_components(self):
        return self.output_frame.world_axis_object_components

    @property
    def pixel_axis_names(self):
        """
        An iterable of strings describing the name for each pixel axis.
        """
        if self.input_frame is not None:
            return self.input_frame.axes_names
        return tuple([""] * self.pixel_n_dim)

    @property
    def world_axis_names(self):
        """
        An iterable of strings describing the name for each world axis.
        """
        if self.output_frame is not None:
            return self.output_frame.axes_names
        return tuple([""] * self.world_n_dim)
